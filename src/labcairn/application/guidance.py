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

**The checks, and the binding.** The memory also holds **checks** — the
questions a reader can run against a manuscript and answer yes or no — and
the **binding** that says which check decides which rule. The check is a
norm, and it lives beside the rules it decides rather than in the chain:
the chain is the mentor's material, and a checklist written down in
advance is not the mentor's material. **The binding is to the version**,
because a rule is a versioned row and a new statement is a new version —
so the check that decides version 1's words is not automatically the check
that decides version 2's. **And a binding is in force only while both of
its ends are**: a withdrawn rule names no check, and a withdrawn check is
named by no rule.

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
    GuidanceCheckRow,
    GuidanceRuleCheckRow,
    GuidanceRuleCounterexampleRow,
    GuidanceRuleRow,
    GuidanceRuleSourceRow,
)
from labcairn.guidance.models import GuidanceCheck, GuidanceRule, RuleCounterexample
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


@dataclass(frozen=True)
class CheckDraft:
    """The fields a check carries, as the memory is about to hold it.

    **The draft is what the layer writes, and it is whole** — the same
    argument the rule's draft makes: a write that took the fields one at a
    time could leave a check half-written, and a half-written check is a
    row the schema refuses and a reader cannot interpret.

    **And the question and the pass criterion travel together.** They are
    different things — a question with no criterion cannot be answered,
    and a criterion with no question decides nothing — so neither may be
    written without the other.
    """

    check_id: str
    question: str
    pass_criterion: str
    proposed_by: str
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


def read_guidance_rule_version(
    context: ApplicationContext, *, rule_id: str, version: int
) -> GuidanceRule:
    """The rule at the version named, with that version's sources and cases.

    **The version asked for, and not the newest.** A new statement is a new
    row, and the old row keeps the state, the sources and the checks it had.
    The highest-version reads answer the retrieval's question — *what does
    this rule say now?* — and they cannot answer the reconciliation's: *what
    did it say then, and what did that version rest on?* A caller comparing a
    rule's past with its present asks here.

    **Everything comes back at that version.** The sources, the
    counterexamples and the checks are stored against ``(rule_id, version)``,
    and :func:`_the_rule` filters all three by the row's own version — so a
    v1 read cannot carry v2's material, and a v2 read cannot carry v1's.

    :raises ApplicationRefusedError: no rule carries that id at that version.
    """
    row = context.store.session.scalar(
        select(GuidanceRuleRow)
        .where(
            GuidanceRuleRow.rule_id == rule_id,
            GuidanceRuleRow.version == version,
        )
        .limit(1)
    )
    if row is None:
        raise guidance_refused(
            GuidanceRefusal.RULE_NOT_FOUND,
            f"no rule carries the id {rule_id!r} at version {version}",
        )
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

    **And the rule's checks are released.** A binding is in force only
    while both of its ends are, so a withdrawn rule names no check: the
    rule is out of force and there is nothing left for its instruments to
    decide. The check rows themselves stay, and a rule that is still in
    force may name them.

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
    _release_rule_bindings(context, rule_id=row.rule_id, version=row.version)
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
# the checks, and the binding
# --------------------------------------------------------------------------- #


def read_guidance_check(context: ApplicationContext, *, check_id: str) -> GuidanceCheck:
    """The check, as the memory holds it.

    :raises ApplicationRefusedError: no check carries that id.
    """
    return _the_check(_the_check_row(context, check_id))


def read_guidance_checks(context: ApplicationContext) -> tuple[GuidanceCheck, ...]:
    """Every check the memory holds, in the order the table holds them.

    **A check nobody has read is still a check**, and this is where the
    whole set is read: the checklist a group wrote down is a list of
    checks, and a reader needs all of them to know what the norm is.
    """
    rows = context.store.session.scalars(select(GuidanceCheckRow)).all()
    return tuple(_the_check(row) for row in rows)


def write_guidance_check(context: ApplicationContext, draft: CheckDraft) -> GuidanceCheck:
    """Write a check, as a candidate.

    **A check is proposed the way a rule is proposed.** What a model
    proposes, a person confirms, and the check lands here as a candidate
    whatever wrote it — a person writing the group's checklist down and a
    distillation run proposing one arrive the same way.

    :param draft: the fields the check carries, whole.
    """
    session = context.store.session
    row = GuidanceCheckRow(
        check_id=draft.check_id,
        question=draft.question,
        pass_criterion=draft.pass_criterion,
        state="candidate",
        proposed_by=draft.proposed_by,
        proposed_at=draft.proposed_at,
    )
    session.add(row)
    session.flush()
    return _the_check(row)


def write_guidance_check_confirmation(
    context: ApplicationContext, *, check_id: str, confirmed_by: str, confirmed_at: datetime
) -> GuidanceCheck:
    """Move the check to ``confirmed``.

    **Only a candidate can be confirmed.** The state machine is the rule's
    own, and a check that has already been confirmed is not a proposal
    any more.

    **The confirmer is whoever the caller named.** Whether that person is
    allowed to confirm is the second-reader rule, and it belongs to
    :mod:`labcairn.guidance.checks`: this operation records the
    confirmation, and the caller that owns the check owns the rule about
    who may give it.

    :raises ApplicationRefusedError: no check carries that id, or the
        check is not a candidate.
    """
    row = _the_check_row(context, check_id)
    if row.state != "candidate":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"a check in state {row.state!r} cannot be confirmed; only a candidate can",
        )
    row.state = "confirmed"
    row.confirmed_by = confirmed_by
    row.confirmed_at = confirmed_at
    context.store.session.flush()
    return _the_check(row)


def write_guidance_check_withdrawal(
    context: ApplicationContext, *, check_id: str, reason: str
) -> GuidanceCheck:
    """Withdraw a check, and release the bindings that named it.

    **The reason is on the row**, for the reason the rule's own withdrawal
    carries one: a retraction that says only "no" is a retraction nobody
    can learn from.

    **And the bindings go with it.** A binding is in force only while both
    of its ends are, so a check that stopped being true decides nothing
    and the rules that named it are unbound. The check itself stays, with
    the reason it was retired — and a rule that named it may name another.

    **And a withdrawal is not twice.** The reason is already on the row,
    and overwriting it would lose the reason the first retraction gave.

    :raises ApplicationRefusedError: no check carries that id, or the
        check is already withdrawn.
    """
    row = _the_check_row(context, check_id)
    if row.state == "withdrawn":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"the check is already withdrawn, for {row.resolution_reason!r}",
        )
    row.state = "withdrawn"
    row.resolution_reason = reason
    _release_check_bindings(context, check_id=check_id)
    context.store.session.flush()
    return _the_check(row)


def write_guidance_rule_check(
    context: ApplicationContext, *, rule_id: str, check_id: str
) -> GuidanceRule:
    """Bind a check to the rule, at the rule's highest version.

    **The binding is to the version, and the version is the rule's
    latest.** A rule that is superseded gets a new version, and the new
    version names no check until somebody binds one: **the check that
    decided the old words is not automatically the check that decides the
    new ones**, and a rewording is not a confirmation.

    **Only a confirmed check may be bound.** A candidate is a proposal,
    and a rule that leans on a proposal leans on nothing that has been
    decided — which is the same rule the memory applies to a rule's own
    confirmer.

    **And a withdrawn rule names no check**, so a binding to one is
    refused: the rule is out of force and there is nothing for the check
    to decide.

    **Binding the same check twice is a no-op, not an error.** The row
    that says it is already there, and the schema's own uniqueness is what
    settles a race between two callers.

    :raises ApplicationRefusedError: no rule carries that id; no check
        carries that id; the check is not confirmed; the rule is
        withdrawn.
    """
    row = _latest(context, rule_id)
    check = read_guidance_check(context, check_id=check_id)
    if check.state != "confirmed":
        raise guidance_refused(
            GuidanceRefusal.CHECK_NOT_CONFIRMED,
            f"the check {check_id!r} is in state {check.state!r}, and a rule may name"
            " only a check a person has confirmed",
        )
    if row.state == "withdrawn":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"the rule is withdrawn, for {row.resolution_reason!r}, and a withdrawn"
            " rule names no check",
        )
    session = context.store.session
    already = session.scalar(
        select(GuidanceRuleCheckRow.id)
        .where(
            GuidanceRuleCheckRow.rule_id == row.rule_id,
            GuidanceRuleCheckRow.version == row.version,
            GuidanceRuleCheckRow.check_id == check_id,
        )
        .limit(1)
    )
    if already is None:
        session.add(
            GuidanceRuleCheckRow(
                rule_id=row.rule_id,
                version=row.version,
                check_id=check_id,
            )
        )
        session.flush()
    return _the_rule(context, row)


def read_guidance_rule_checks(
    context: ApplicationContext, *, rule_id: str
) -> tuple[GuidanceCheck, ...]:
    """The checks that decide the rule, at its highest version.

    **At the highest version, because that is the rule the memory
    serves.** A rule that was superseded and whose new version names no
    check has no checks, and saying so is the answer.

    :raises ApplicationRefusedError: no rule carries that id.
    """
    row = _latest(context, rule_id)
    return _the_checks(context, rule_id=row.rule_id, version=row.version)


def read_guidance_check_rules(
    context: ApplicationContext, *, check_id: str
) -> tuple[GuidanceRule, ...]:
    """The rules the check decides, at each rule's highest version.

    **This is the question the binding was made for**: a student holding
    a checklist item asks which rule it is checking, and the answer is
    the rules that name it.

    **At each rule's highest version.** A rule that named the check at an
    older version does not appear, because the reader is asking about the
    rule as it stands — and the memory serves the highest version.
    """
    session = context.store.session
    rule_ids = tuple(
        session.scalars(
            select(GuidanceRuleCheckRow.rule_id)
            .where(GuidanceRuleCheckRow.check_id == check_id)
            .distinct()
            .order_by(GuidanceRuleCheckRow.rule_id)
        )
    )
    rules: list[GuidanceRule] = []
    for bound_rule_id in rule_ids:
        row = _latest(context, bound_rule_id)
        bound = session.scalar(
            select(GuidanceRuleCheckRow.id)
            .where(
                GuidanceRuleCheckRow.rule_id == bound_rule_id,
                GuidanceRuleCheckRow.version == row.version,
                GuidanceRuleCheckRow.check_id == check_id,
            )
            .limit(1)
        )
        if bound is None:
            continue
        rules.append(_the_rule(context, row))
    return tuple(rules)


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
    """One row, its sources, its cases and its checks, as the memory serves them.

    **The sources are ordered by the chain's key and the cases by the order
    they were recorded**, so two reads of the same rule give the same rule.
    **The checks are ordered by the check's own id**, for the same reason:
    a reader that reads the rule twice reads the same list of instruments
    twice.
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
        checks=_the_checks(context, rule_id=row.rule_id, version=row.version),
    )


def _the_check_row(context: ApplicationContext, check_id: str) -> GuidanceCheckRow:
    """The check, or the refusal that says it is not there."""
    row = context.store.session.scalar(
        select(GuidanceCheckRow).where(GuidanceCheckRow.check_id == check_id).limit(1)
    )
    if row is None:
        raise guidance_refused(
            GuidanceRefusal.CHECK_NOT_FOUND,
            f"no check carries the id {check_id!r}",
        )
    return row


def _the_check(row: GuidanceCheckRow) -> GuidanceCheck:
    """One row, as the memory serves it."""
    return GuidanceCheck(
        check_id=row.check_id,
        question=row.question,
        pass_criterion=row.pass_criterion,
        state=row.state,
        proposed_by=row.proposed_by,
        proposed_at=row.proposed_at,
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
        resolution_reason=row.resolution_reason,
    )


def _the_checks(
    context: ApplicationContext, *, rule_id: str, version: int
) -> tuple[GuidanceCheck, ...]:
    """The checks bound to that version of the rule, ordered by their ids.

    **At the version, and not at the rule.** The binding belongs to the
    words it was made against, so a rule's older version keeps its own
    checks and the newest version starts with none.
    """
    session = context.store.session
    check_ids = tuple(
        session.scalars(
            select(GuidanceRuleCheckRow.check_id)
            .where(
                GuidanceRuleCheckRow.rule_id == rule_id,
                GuidanceRuleCheckRow.version == version,
            )
            .order_by(GuidanceRuleCheckRow.check_id)
        )
    )
    if not check_ids:
        return ()
    return tuple(
        _the_check(row)
        for row in session.scalars(
            select(GuidanceCheckRow)
            .where(GuidanceCheckRow.check_id.in_(check_ids))
            .order_by(GuidanceCheckRow.check_id)
        )
    )


def _release_check_bindings(context: ApplicationContext, *, check_id: str) -> None:
    """The rows that bound this check, gone.

    **A binding is in force only while both of its ends are**, so a check
    that is withdrawn is named by no rule.
    """
    session = context.store.session
    for row in session.scalars(
        select(GuidanceRuleCheckRow).where(GuidanceRuleCheckRow.check_id == check_id)
    ).all():
        session.delete(row)


def _release_rule_bindings(context: ApplicationContext, *, rule_id: str, version: int) -> None:
    """The rows that bound this version of the rule, gone.

    **A withdrawn rule names no check**: the rule is out of force, and the
    instruments it held are released to the rules that are still in it.
    The older versions keep their own bindings, because they are what
    they were bound against.
    """
    session = context.store.session
    for row in session.scalars(
        select(GuidanceRuleCheckRow).where(
            GuidanceRuleCheckRow.rule_id == rule_id,
            GuidanceRuleCheckRow.version == version,
        )
    ).all():
        session.delete(row)


__all__ = [
    "CheckDraft",
    "RuleDraft",
    "read_guidance_check",
    "read_guidance_check_rules",
    "read_guidance_checks",
    "read_guidance_rule",
    "read_guidance_rule_checks",
    "read_guidance_rule_version",
    "read_guidance_rules",
    "write_guidance_check",
    "write_guidance_check_confirmation",
    "write_guidance_check_withdrawal",
    "write_guidance_counterexample",
    "write_guidance_rule_check",
    "write_guidance_rule_confirmation",
    "write_guidance_rule_resolution",
    "write_guidance_rule_version",
    "write_guidance_rule_withdrawal",
]
