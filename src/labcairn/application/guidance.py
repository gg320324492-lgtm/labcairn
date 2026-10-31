"""The guidance memory's rules: the lifecycle's reads and writes, through the layer.

**What this module is.** The mentor line's rule memory is three tables —
``guidance_rules``, ``guidance_rule_sources`` and
``guidance_rule_counterexamples`` — and the modules that reason over them
used to read and write those rows directly, by importing
``labcairn.db.models`` and writing their own ``select(...)`` statements.
**That is the arrangement the application layer exists to prevent**: a
caller that reaches the store directly is a caller the capability model does
not reach, and a guard applied to an operation would apply to some of the
callers and not the others.

So the memory's reads and writes live here, and
:mod:`labcairn.guidance.rules`, :mod:`labcairn.guidance.retrieval` and
:mod:`labcairn.guidance.distil` call these operations instead of the store.

**And these writes do not commit; the caller holds the transaction.** The
memory's writes are flushed and left for the caller's unit of work to
commit, because a rule's state and the event that describes it have to
land together. **A caller that writes through this module inside the
store's own ``unit(...)`` gets a committed write; a caller that writes
through it outside one gets a write that is lost when the session
closes.** That is not a hypothetical: the rule door's API route was the
first caller to arrive without a unit, and the rule it had just confirmed
was back to ``candidate`` the moment the request ended. The route now
holds the unit, and the two witnesses that watch the door read the rule
back **through another request** — each request forks its own session, so
a write that did not land cannot pass for one that did.

**What these operations refuse.** The memory's own reasons, in the layer's
vocabulary: a rule that is not there, and a transition the closed state
machine does not have. The rules about **words and people** — the closed
vocabulary of problems, the fields that may not be empty, the source a rule
must name, the second reader who may not be the proposer — stay with the
module that owns them, because they are about what the caller said rather
than about what a row may hold.

**And the state machine is here because a row may not hold it.** A layer
operation that could write a state the memory forbids would be a hole in the
layer, so the transition that moves a rule out of ``candidate`` is the layer's
to refuse — and :mod:`labcairn.guidance.rules` asks it rather than restating
it. **The contract is asked, not restated.**

**What these operations do not do.** They do not run a check, they do not
accept a model's proposal, and they do not read the material a rule was
learned from. **The permission that governs what a reader may be shown is
the permission on the material**, and it is asked where the material is
named — the retrieval asks it per source at serve time and drops the sources
the reader may not reach (ADR-0003 C5). These operations are the only way to
the rows, and a guard added here reaches **every** caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import guidance_refused
from labcairn.db.models import (
    GuidanceRuleCounterexampleRow,
    GuidanceRuleRow,
    GuidanceRuleSourceRow,
)
from labcairn.guidance.models import GuidanceRule, RuleCounterexample
from labcairn.guidance.refusals import GuidanceRefusal


@dataclass(frozen=True)
class RuleDraft:
    """The fields a rule carries, as the memory is about to hold it.

    **The draft is what the layer writes, and it is whole.** A write that
    took the fields one at a time could leave a rule half-written — a
    statement without its scope, a version without its sources — and a
    half-written rule is a row the schema refuses and a reader cannot
    interpret. So the fields travel together, and the layer writes them
    together.
    """

    rule_id: str
    version: int
    issue_type: str
    statement: str
    #: The rule's own ``context`` field, under the name the draft uses for
    #: it: the situation a reader would recognise.
    rule_context: str
    scope: str
    example: str
    proposed_by: str
    #: The chain material the rule is learned from, by the chain's own key.
    sources: tuple[str, ...]
    proposed_at: datetime


def read_guidance_rule(context: ApplicationContext, *, rule_id: str) -> GuidanceRule:
    """The rule at its highest version, with its sources and its cases.

    **The cases come back in the same read.** A counterexample is part of the
    answer, not a footnote beside it, and a reader that had to ask twice
    could be answered twice differently.

    :raises ApplicationRefusedError: no rule carries that id.
    """
    row = _latest(context, rule_id)
    return _the_rule(context, row)


def read_guidance_rules(context: ApplicationContext) -> tuple[GuidanceRule, ...]:
    """The highest version of every rule, with its sources and its cases.

    **The old rows stay in the table and out of the results** — the memory
    keeps its past, and a reader sees each rule's newest words and nothing
    else. The rules come back in the order the table holds them; a caller
    that needs an order of its own makes one, and the retrieval's order is
    by state and by the rule's own id.
    """
    newest: dict[str, GuidanceRuleRow] = {}
    for row in context.store.session.scalars(select(GuidanceRuleRow)).all():
        held = newest.get(row.rule_id)
        if held is None or row.version > held.version:
            newest[row.rule_id] = row
    return tuple(_the_rule(context, row) for row in newest.values())


def write_guidance_rule_version(context: ApplicationContext, draft: RuleDraft) -> GuidanceRule:
    """Write a version of a rule and the sources it is bound to.

    **The row and its source bindings are written together.** A rule whose
    sources were not bound would be a rule nobody can check — a rule without
    a source is not a rule — and a rule bound to sources it does not have
    would be a pointer to nothing.

    **The version is a candidate.** A new statement is a new row and it
    starts as a candidate, whatever wrote it; a person or a distillation
    run lands here the same way, and only a second reader moves it on.

    :param draft: the fields the rule carries, whole.
    """
    session = context.store.session
    row = GuidanceRuleRow(
        rule_id=draft.rule_id,
        version=draft.version,
        issue_type=draft.issue_type,
        statement=draft.statement,
        context=draft.rule_context,
        scope=draft.scope,
        example=draft.example,
        state="candidate",
        proposed_by=draft.proposed_by,
        proposed_at=draft.proposed_at,
    )
    session.add(row)
    session.add_all(
        GuidanceRuleSourceRow(rule_id=draft.rule_id, version=draft.version, issue_key=key)
        for key in draft.sources
    )
    session.flush()
    return _the_rule(context, row)


def write_guidance_rule_confirmation(
    context: ApplicationContext,
    *,
    rule_id: str,
    confirmed_by: str,
    confirmed_at: datetime,
) -> GuidanceRule:
    """Move the rule at its highest version to ``confirmed``.

    **Only a candidate can be confirmed.** The state machine is closed
    (ADR-0016 D8), and a rule that has already been confirmed is not a
    proposal any more — confirming it again would overwrite a decision
    rather than make one.

    **The confirmer is whoever the caller named.** Whether that person is
    allowed to confirm is the second-reader rule, and it belongs to
    :mod:`labcairn.guidance.rules`: this operation records the
    confirmation, and the caller that owns the rule owns the rule about
    who may give it.

    :raises ApplicationRefusedError: no rule carries that id, or the rule
        is not a candidate.
    """
    row = _latest(context, rule_id)
    if row.state != "candidate":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"a rule in state {row.state!r} cannot be confirmed; only a candidate can",
        )
    row.state = "confirmed"
    row.confirmed_by = confirmed_by
    row.confirmed_at = confirmed_at
    context.store.session.flush()
    return _the_rule(context, row)


def write_guidance_rule_resolution(
    context: ApplicationContext,
    *,
    rule_id: str,
    reason: str,
    disputed_by: str,
    now: datetime,
) -> GuidanceRule:
    """Move the rule at its highest version to ``disputed``.

    **Disputing is not retracting.** A disputed rule stays in the memory and
    is served *with* the case against it, because a rule challenged once is
    a rule a reader may still judge.

    **A withdrawn rule cannot be disputed.** A retraction says the rule
    stopped being true, and disputing it after the fact would put two
    answers on one row; the way to say a new thing is a new version.

    :raises ApplicationRefusedError: no rule carries that id, or the rule
        is already withdrawn.
    """
    row = _latest(context, rule_id)
    if row.state == "withdrawn":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            "a withdrawn rule cannot be disputed; propose a new version instead",
        )
    row.state = "disputed"
    row.resolution_reason = reason
    row.confirmed_at = row.confirmed_at if row.confirmed_at is not None else now
    row.confirmed_by = row.confirmed_by or disputed_by
    context.store.session.flush()
    return _the_rule(context, row)


def write_guidance_rule_withdrawal(
    context: ApplicationContext, *, rule_id: str, reason: str
) -> GuidanceRule:
    """Move the rule at its highest version to ``withdrawn``.

    **The reason is on the row.** A withdrawn rule is how the memory says
    *this stopped being true*, and a retraction that says only "no" is a
    retraction nobody can learn from.

    **And a withdrawal is not twice.** The reason is already on the row,
    and overwriting it would lose the reason the first retraction gave.

    :raises ApplicationRefusedError: no rule carries that id, or the rule
        is already withdrawn.
    """
    row = _latest(context, rule_id)
    if row.state == "withdrawn":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"the rule is already withdrawn, for {row.resolution_reason!r}",
        )
    row.state = "withdrawn"
    row.resolution_reason = reason
    context.store.session.flush()
    return _the_rule(context, row)


def write_guidance_counterexample(
    context: ApplicationContext,
    *,
    rule_id: str,
    statement: str,
    recorded_by: str,
    recorded_at: datetime,
    issue_key: str | None,
) -> GuidanceRule:
    """Record the case where the rule does not hold, against its latest version.

    **The case is bound to a version.** A rule that is later reworded keeps
    the cases that were recorded against the wording they challenged, and
    the new version starts with none — because a case against the old words
    is not a case against the new ones.

    :raises ApplicationRefusedError: no rule carries that id.
    """
    session = context.store.session
    row = _latest(context, rule_id)
    session.add(
        GuidanceRuleCounterexampleRow(
            rule_id=row.rule_id,
            version=row.version,
            statement=statement,
            issue_key=issue_key,
            recorded_by=recorded_by,
            recorded_at=recorded_at,
        )
    )
    session.flush()
    return _the_rule(context, row)


# --------------------------------------------------------------------------- #
# the store's answers
# --------------------------------------------------------------------------- #


def _latest(context: ApplicationContext, rule_id: str) -> GuidanceRuleRow:
    """The highest version of the rule, or the refusal that says it is not there.

    **The highest version, and not the first.** A new statement is a new row
    and the old one keeps the state it had, so the rule a reader means is the
    newest wording of it — and the older rows stay readable for anyone who
    asks for them by version.
    """
    row = context.store.session.scalar(
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


def _the_rule(context: ApplicationContext, row: GuidanceRuleRow) -> GuidanceRule:
    """One row, its sources and its cases, as the memory serves them.

    **The sources are ordered by the chain's key and the cases by the order
    they were recorded**, so two reads of the same rule give the same rule.
    """
    session = context.store.session
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


__all__ = [
    "RuleDraft",
    "read_guidance_rule",
    "read_guidance_rules",
    "write_guidance_counterexample",
    "write_guidance_rule_confirmation",
    "write_guidance_rule_resolution",
    "write_guidance_rule_version",
    "write_guidance_rule_withdrawal",
]
