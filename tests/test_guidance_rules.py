"""The guidance memory: a rule that carries its sources, and the second reader.

**What is under test.** LC-P2-11 T00 and T01: ``guidance_rules``, its
sources and its counterexamples, and the lifecycle API that proposes,
confirms, disputes, withdraws and supersedes.

======================================================  =========================
     a rule is a row                                     every field the work
                                                          order lists, plus its
                                                          sources and its cases
     the problem is from the vocabulary                  a label outside the
                                                          thirteen is refused
     a rule without a source is not a rule               the API refuses it, and
                                                          the schema would too
     the work order's "must not" row                     an empty field is
                                                          refused by API and by
                                                          schema
     the state machine is closed                         an illegal state is
                                                          refused by the database
     a confirmed rule names its confirmer                the database refuses a
                                                          confirmation without a
                                                          name
     **the confirmer is a second reader**                the proposer confirming
                                                          their own rule is
                                                          refused, and a second
                                                          reader's confirmation
                                                          lands
     a dispute and a retraction carry their reason       a shrug is refused
     a new statement is a new row                        the old version keeps
                                                          its state; the new one
                                                          is a candidate again
      a counterexample travels with the rule              served in the same read,
                                                          or refused when empty
======================================================  =========================

**Why the schema's refusals are witnessed by writing rows.** The project's
lesson from revision 0007, in the words the feedback tests already carry:
*"the parity test passed through it, because the migration and the ORM were
mangled identically."* So each schema rule is witnessed by **writing a row
the schema must refuse** with a raw ``INSERT`` that bypasses the ORM, and
watching the database refuse it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.tasks import create_task
from labcairn.db.models import GuidanceCheckRow, GuidanceRuleCheckRow, GuidanceRuleRow
from labcairn.guidance.checks import (
    bind_check,
    confirm_check,
    propose_check,
    read_check_rules,
    read_rule_checks,
    withdraw_check,
)
from labcairn.guidance.models import GuidanceCheck
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.guidance.rules import (
    GuidanceRule,
    confirm_rule,
    dispute_rule,
    propose_rule,
    read_rule,
    record_counterexample,
    supersede_rule,
    withdraw_rule,
)
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)


def allow_all() -> PermissionPolicy:
    """A policy that permits everything, for a test about something else."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture()
def memory(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A migrated store and a context, with no manuscript: the memory is a table."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    created = create_task(
        store=store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Recording the guidance memory",
        goal=TaskGoal(
            objective="Record what the advisor's rules say and where they came from.",
            success_criterion="A rule a reader can trace to its source.",
        ),
        source_dirs=(),
        now=MOMENT,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=allow_all(),
        ledger=ApprovalLedger(),
    )


def _propose(
    context: ApplicationContext,
    *,
    issue_type: str = "method_and_hypothesis",
    statement: str = "When the claim rests on a comparison, the advisor asks"
    " for the baseline to be named in the same paragraph.",
    sources: tuple[str, ...] = ("iss-gold-a-r1",),
    proposed_by: str = "distil-run-7",
    checks: tuple[str, ...] = (),
) -> GuidanceRule:
    return propose_rule(
        context,
        issue_type=issue_type,
        statement=statement,
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        sources=sources,
        proposed_by=proposed_by,
        now=MOMENT,
        checks=checks,
    )


#: The check this file's witnesses use. **Invented, and not the group's
#: wording**: what goes into the tree is the shape of a check, not a
#: checklist somebody else wrote.
QUESTION = "Does every paragraph that carries a comparison name what it compares against?"
CRITERION = "The paragraph names the quantity the comparison is against, in absolute terms."


def _propose_check(
    context: ApplicationContext,
    *,
    question: str = QUESTION,
    pass_criterion: str = CRITERION,
    proposed_by: str = "the-group",
) -> GuidanceCheck:
    """A check as it is proposed: a candidate, and nobody has confirmed it."""
    return propose_check(
        context,
        question=question,
        pass_criterion=pass_criterion,
        proposed_by=proposed_by,
        now=MOMENT,
    )


def _confirmed_check(
    context: ApplicationContext,
    *,
    question: str = QUESTION,
    pass_criterion: str = CRITERION,
    proposed_by: str = "the-group",
) -> GuidanceCheck:
    """A check a second reader has confirmed, and a rule may therefore name."""
    proposed = _propose_check(
        context, question=question, pass_criterion=pass_criterion, proposed_by=proposed_by
    )
    return confirm_check(context, check_id=proposed.check_id, confirmed_by="the-advisor", now=LATER)


def _refusal(call: object) -> GuidanceRefusal:
    """The guidance refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return GuidanceRefusal(call.reason.value.removeprefix("guidance_"))


def test_a_rule_carries_a_problem_a_context_a_scope_a_counterexample_and_a_version(
    memory: ApplicationContext,
) -> None:
    """The work order's own row: every field the memory holds, filled.

    **The cases are an empty tuple, not a null.** A rule proposed before
    anybody challenged it has no counterexamples, and the read still
    carries the collection — an empty tuple says the memory holds none,
    not that it did not look. **And a recorded case travels from the
    next read on**: the row is the unit the cases bind to.
    """
    rule = _propose(memory, sources=("iss-gold-a-r1", "iss-gold-a-r2"))
    read_back = read_rule(memory, rule_id=rule.rule_id)
    assert read_back.state == "candidate"
    assert read_back.version == 1
    for field in (
        read_back.issue_type,
        read_back.statement,
        read_back.context,
        read_back.scope,
        read_back.example,
    ):
        assert field.strip(), "a rule with an empty field is the work order's must-not row"
    assert read_back.proposed_by == "distil-run-7"
    assert read_back.confirmed_by is None
    assert read_back.confirmed_at is None
    assert read_back.resolution_reason is None
    assert read_back.sources == ("iss-gold-a-r1", "iss-gold-a-r2")
    assert read_back.counterexamples == ()
    challenged = record_counterexample(
        memory,
        rule_id=rule.rule_id,
        statement="The ablation paragraph of 2026-03-09 named its baseline.",
        recorded_by="reader-2",
        now=LATER,
    )
    assert len(challenged.counterexamples) == 1
    assert read_rule(memory, rule_id=rule.rule_id).version == 1


def test_a_problem_outside_the_vocabulary_is_refused(
    memory: ApplicationContext,
) -> None:
    """a label outside the thirteen is refused, at the boundary with a name."""
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose(memory, issue_type="advisor_preference")
    assert _refusal(raised.value) is GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY, raised.value


def test_a_rule_without_a_source_is_refused(memory: ApplicationContext) -> None:
    """a rule that names no chain material is not stored.

    **The database cannot count a rule's sources** — a cross-table CHECK
    is not SQLite's to give — so this is the API's refusal, and the
    witness for the schema's half is that the schema holds the rows the
    API does write.
    """
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose(memory, sources=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE, raised.value


def test_an_empty_field_is_refused(memory: ApplicationContext) -> None:
    """the work order's "must not" row — a rule with nothing in it."""
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose(memory, statement="   ")
    assert _refusal(raised.value) is GuidanceRefusal.RULE_FIELD_EMPTY, raised.value


def _raw_insert(session: Session, **overrides: object) -> None:
    """Write a rule row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "rule_id": "rule-raw",
        "version": 1,
        "issue_type": "method_and_hypothesis",
        "statement": "The advisor asks for the baseline to be named.",
        "context": "A results section whose claim is comparative.",
        "scope": "Empirical papers.",
        "example": "The comment of 2026-03-02.",
        "state": "candidate",
        "proposed_by": "distil-run-7",
        "proposed_at": MOMENT,
    }
    values.update(overrides)
    session.add(GuidanceRuleRow(**values))
    session.flush()


def test_the_schema_refuses_what_the_api_refuses(env: StoreEnv) -> None:
    """At the schema: the rows the database itself must refuse.

    **Each refusal is witnessed by the database refusing, not by reading
    the constraint** — the lesson of revision 0007 is that a constraint
    nobody has violated is a comment.
    """
    refusals: tuple[dict[str, object], ...] = (
        {"issue_type": "advisor_preference"},
        {"state": "proposed"},
        {"statement": ""},
        {"scope": ""},
        {"state": "confirmed"},
        {"state": "confirmed", "confirmed_by": "reader-2"},
        {"state": "confirmed", "confirmed_by": "", "confirmed_at": LATER},
        {"state": "candidate", "confirmed_by": "reader-2"},
        {"state": "withdrawn"},
        {"state": "disputed", "resolution_reason": "   "},
        {"state": "candidate", "resolution_reason": "a reason on a live rule"},
    )
    for overrides in refusals:
        session = env.new_session()
        try:
            try:
                _raw_insert(session, **overrides)
            except IntegrityError:
                pass
            else:
                pytest.fail(f"the schema accepted a row it must refuse: {overrides}")
        finally:
            session.rollback()
            session.close()


def test_the_proposer_cannot_confirm_their_own_rule(
    memory: ApplicationContext,
) -> None:
    """the second-reader rule, as the owner wrote it on 2026-10-31.

    **One person reading twice is one person reading once with extra
    steps.** The rule was written for the gold set's readings; a rule's
    confirmer is that rule's arbiter, and the refusal carries the
    proposer's name so the caller learns who was missing.
    """
    rule = _propose(memory, proposed_by="distil-run-7")
    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(memory, rule_id=rule.rule_id, confirmed_by="distil-run-7", now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER, raised.value


def test_a_second_reader_confirms_the_rule(memory: ApplicationContext) -> None:
    """The other way round: a different person's confirmation lands."""
    rule = _propose(memory, proposed_by="distil-run-7")
    confirmed = confirm_rule(memory, rule_id=rule.rule_id, confirmed_by="the-advisor", now=LATER)
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_by == "the-advisor"
    assert confirmed.confirmed_at == LATER


def test_confirming_twice_is_refused(memory: ApplicationContext) -> None:
    """The state machine is closed: only a candidate can be confirmed."""
    rule = _propose(memory)
    confirm_rule(memory, rule_id=rule.rule_id, confirmed_by="the-advisor", now=LATER)
    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(memory, rule_id=rule.rule_id, confirmed_by="reader-3", now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.TRANSITION_NOT_POSSIBLE, raised.value


def test_a_dispute_and_a_retraction_carry_their_reason(
    memory: ApplicationContext,
) -> None:
    """a shrug is refused, in both of the resolution's forms."""
    disputed = _propose(memory)
    with pytest.raises(ApplicationRefusedError) as raised:
        dispute_rule(
            memory, rule_id=disputed.rule_id, reason="   ", disputed_by="reader-2", now=LATER
        )
    assert _refusal(raised.value) is GuidanceRefusal.RESOLUTION_WITHOUT_REASON, raised.value

    disputed = dispute_rule(
        memory,
        rule_id=disputed.rule_id,
        reason="The two cases in the corpus where the baseline was already named.",
        disputed_by="reader-2",
        now=LATER,
    )
    assert disputed.state == "disputed"

    withdrawn = _propose(memory, statement="A different rule, for the second read.")
    with pytest.raises(ApplicationRefusedError) as raised:
        withdraw_rule(memory, rule_id=withdrawn.rule_id, reason="", now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.RESOLUTION_WITHOUT_REASON, raised.value

    withdrawn = withdraw_rule(
        memory,
        rule_id=withdrawn.rule_id,
        reason="The source response was re-judged as not addressed.",
        now=LATER,
    )
    assert withdrawn.state == "withdrawn"
    assert withdrawn.resolution_reason is not None
    with pytest.raises(ApplicationRefusedError) as raised:
        dispute_rule(
            memory, rule_id=withdrawn.rule_id, reason="after the fact", disputed_by="r", now=LATER
        )
    assert _refusal(raised.value) is GuidanceRefusal.TRANSITION_NOT_POSSIBLE, raised.value


def test_a_new_statement_is_a_new_row(memory: ApplicationContext) -> None:
    """the memory does not edit its past.

    **The old version keeps the state it had, and the new version is a
    candidate that needs a second reader like any other** — a rewording
    is not a confirmation.
    """
    rule = _propose(memory, proposed_by="distil-run-7")
    confirm_rule(memory, rule_id=rule.rule_id, confirmed_by="the-advisor", now=LATER)
    replacement = supersede_rule(
        memory,
        rule_id=rule.rule_id,
        statement="When the claim rests on a comparison, the advisor names the"
        " baseline and the effect size in the same paragraph.",
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        issue_type="method_and_hypothesis",
        sources=("iss-gold-a-r1",),
        proposed_by="distil-run-8",
        now=LATER,
    )
    assert replacement.version == 2
    assert replacement.state == "candidate"
    assert replacement.confirmed_by is None
    read_back = read_rule(memory, rule_id=rule.rule_id)
    assert read_back.version == 2
    # The old row keeps the state it had, and the memory holds both.
    rows = memory.store.session.query(GuidanceRuleRow).all()
    assert sorted(row.version for row in rows) == [1, 2]
    old = next(row for row in rows if row.version == 1)
    assert old.state == "confirmed"


def test_a_counterexample_travels_with_the_rule(memory: ApplicationContext) -> None:
    """the case against the rule comes back in the same read.

    **And an empty case challenges nothing** — the refusal is named, not
    silent.
    """
    rule = _propose(memory)
    challenged = record_counterexample(
        memory,
        rule_id=rule.rule_id,
        statement="The ablation paragraph of 2026-03-09 named its baseline,"
        " and the advisor said nothing.",
        recorded_by="reader-2",
        now=LATER,
        issue_key="iss-gold-a-r2",
    )
    assert len(challenged.counterexamples) == 1
    case = challenged.counterexamples[0]
    assert case.recorded_by == "reader-2"
    assert case.issue_key == "iss-gold-a-r2"
    # Recording a case does not move the rule: whether it is disputed is a
    # reader's decision, not the record's.
    assert challenged.state == "candidate"

    with pytest.raises(ApplicationRefusedError) as raised:
        record_counterexample(
            memory,
            rule_id=rule.rule_id,
            statement="   ",
            recorded_by="reader-2",
            now=LATER,
        )
    assert _refusal(raised.value) is GuidanceRefusal.COUNTEREXAMPLE_EMPTY, raised.value


def test_a_rule_that_is_not_there_is_refused(memory: ApplicationContext) -> None:
    """The memory says what is missing, by name."""
    with pytest.raises(ApplicationRefusedError) as raised:
        read_rule(memory, rule_id="rule-nowhere")
    assert _refusal(raised.value) is GuidanceRefusal.RULE_NOT_FOUND, raised.value


# --------------------------------------------------------------------------- #
# the checks, and the binding
# --------------------------------------------------------------------------- #


def test_a_check_carries_its_question_and_its_criterion(memory: ApplicationContext) -> None:
    """A check is decidable, and decidability is two things.

    **The question is what the reader asks and the criterion is what would
    pass**, and they are not the same field: a question with no criterion
    cannot be answered, and a criterion with no question decides nothing.
    So the check holds both, and a reader can see which is which.
    """
    check = _confirmed_check(memory)
    assert check.question.strip()
    assert check.pass_criterion.strip()
    assert check.question != check.pass_criterion
    assert check.state == "confirmed"
    assert check.confirmed_by == "the-advisor"
    assert check.confirmed_at == LATER
    assert check.proposed_by == "the-group"


def test_an_empty_check_field_is_refused(memory: ApplicationContext) -> None:
    """The check's "must not" row: a check with nothing in it.

    **Both of the two fields are refused by name**, because a check that
    keeps one of them is half a check and the half is the part a reader
    would act on.
    """
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose_check(memory, question="   ")
    assert _refusal(raised.value) is GuidanceRefusal.CHECK_FIELD_EMPTY, raised.value

    with pytest.raises(ApplicationRefusedError) as raised:
        _propose_check(memory, pass_criterion="  ")
    assert _refusal(raised.value) is GuidanceRefusal.CHECK_FIELD_EMPTY, raised.value


def test_the_proposer_cannot_confirm_their_own_check(memory: ApplicationContext) -> None:
    """the second-reader rule, on the check as well as on the rule.

    **What a model proposes, a person confirms** — and the same person may
    not do both. One person reading twice is one person reading once with
    extra steps.
    """
    proposed = _propose_check(memory)
    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_check(memory, check_id=proposed.check_id, confirmed_by="the-group", now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER, raised.value


def test_a_rule_may_name_only_a_confirmed_check(memory: ApplicationContext) -> None:
    """A candidate is a proposal, and a rule may not lean on one.

    **And the refusal comes before the rule is written**, so a rule that
    could not be bound is never half-written.
    """
    proposed = _propose_check(memory)
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose(memory, checks=(proposed.check_id,))
    assert _refusal(raised.value) is GuidanceRefusal.CHECK_NOT_CONFIRMED, raised.value
    assert memory.store.session.query(GuidanceRuleRow).all() == [], (
        "a rule that could not name its check was written anyway"
    )

    rule = _propose(memory)
    with pytest.raises(ApplicationRefusedError) as raised:
        bind_check(memory, rule_id=rule.rule_id, check_id=proposed.check_id)
    assert _refusal(raised.value) is GuidanceRefusal.CHECK_NOT_CONFIRMED, raised.value
    assert read_rule(memory, rule_id=rule.rule_id).checks == ()


def test_a_rule_names_the_checks_that_decide_it(memory: ApplicationContext) -> None:
    """The binding, in both directions.

    **This is what the binding was made for.** A student holding a
    checklist item asks which rule it is checking, and the memory answers
    — and a rule the reader reads back carries the checks that decide it,
    so the two documents are one.
    """
    check = _confirmed_check(memory)
    rule = _propose(memory, checks=(check.check_id,))

    assert [bound.check_id for bound in rule.checks] == [check.check_id]
    assert read_rule(memory, rule_id=rule.rule_id).checks == (check,)

    decided = read_check_rules(memory, check_id=check.check_id)
    assert [ruled.rule_id for ruled in decided] == [rule.rule_id]
    assert decided[0].checks == (check,)
    assert [bound.check_id for bound in read_rule_checks(memory, rule_id=rule.rule_id)] == [
        check.check_id
    ]


def test_two_rules_may_share_one_check(memory: ApplicationContext) -> None:
    """The checklist is generic, and one item may decide more than one rule.

    **A check that could be named by only one rule would have to be written
    once per rule**, and the memory would hold two different questions with
    the same answer.
    """
    check = _confirmed_check(memory)
    first = _propose(memory, checks=(check.check_id,))
    second = _propose(
        memory,
        statement="When the claim rests on a comparison, the advisor asks"
        " for the effect size beside the baseline.",
        sources=("iss-gold-b-r1",),
        checks=(check.check_id,),
    )
    decided = read_check_rules(memory, check_id=check.check_id)
    assert [ruled.rule_id for ruled in decided] == sorted([first.rule_id, second.rule_id])
    assert [bound.check_id for bound in first.checks] == [check.check_id]
    assert [bound.check_id for bound in second.checks] == [check.check_id]


def test_a_withdrawn_rule_names_no_check(memory: ApplicationContext) -> None:
    """A rule that is out of force decides nothing, so it holds no check.

    **And the check is free for another rule to name** — which is what
    makes "a check no rule names" an answerable question at all.
    """
    check = _confirmed_check(memory)
    rule = _propose(memory, checks=(check.check_id,))
    withdrawn = withdraw_rule(
        memory,
        rule_id=rule.rule_id,
        reason="The advisor stopped asking for the baseline to be named.",
        now=LATER,
    )
    assert withdrawn.checks == ()
    assert read_rule(memory, rule_id=rule.rule_id).checks == ()
    assert read_check_rules(memory, check_id=check.check_id) == ()


def test_a_new_version_starts_with_no_check(memory: ApplicationContext) -> None:
    """The binding belongs to the version, and a new version is a new claim.

    **The old version keeps what it was bound against** — the memory does
    not edit its past — **and the new version names no check until a
    person binds one.** The check that decided the old words is not
    automatically the check that decides the new ones.
    """
    check = _confirmed_check(memory)
    rule = _propose(memory, checks=(check.check_id,))
    confirm_rule(memory, rule_id=rule.rule_id, confirmed_by="the-advisor", now=LATER)

    replacement = supersede_rule(
        memory,
        rule_id=rule.rule_id,
        statement="When the claim rests on a comparison, the advisor names the"
        " baseline and the effect size in the same paragraph.",
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        issue_type="method_and_hypothesis",
        sources=("iss-gold-a-r1",),
        proposed_by="distil-run-8",
        now=LATER,
    )
    assert replacement.version == 2
    assert replacement.checks == ()
    assert read_rule(memory, rule_id=rule.rule_id).checks == ()

    held = memory.store.session.query(GuidanceRuleCheckRow).all()
    assert [(row.rule_id, row.version) for row in held] == [(rule.rule_id, 1)], (
        "the old version's binding did not stay with the version it was made against"
    )


def test_a_withdrawn_check_is_named_by_no_rule(memory: ApplicationContext) -> None:
    """A check that stopped being the test decides nothing.

    **And the check itself stays**, with the reason it was retired, so a
    rule that is still in force may name another check and a reader can
    see what happened to this one.
    """
    check = _confirmed_check(memory)
    rule = _propose(memory, checks=(check.check_id,))
    withdrawn = withdraw_check(
        memory,
        check_id=check.check_id,
        reason="The criterion was found not to be decidable from the text.",
        now=LATER,
    )
    assert withdrawn.state == "withdrawn"
    assert withdrawn.resolution_reason is not None
    assert read_check_rules(memory, check_id=check.check_id) == ()
    assert read_rule(memory, rule_id=rule.rule_id).checks == ()


def _raw_insert_check(session: Session, **overrides: object) -> None:
    """Write a check row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "check_id": "check-raw",
        "question": "Does every comparison name what it compares against?",
        "pass_criterion": "The paragraph names the quantity compared against.",
        "state": "candidate",
        "proposed_by": "the-group",
        "proposed_at": MOMENT,
    }
    values.update(overrides)
    session.add(GuidanceCheckRow(**values))
    session.flush()


def test_the_schema_refuses_what_the_api_refuses_about_the_checks(env: StoreEnv) -> None:
    """At the schema: the check rows the database itself must refuse.

    **Each refusal is witnessed by the database refusing**, for the reason
    revision 0007 records: a constraint nobody has violated is a comment.
    """
    refusals: tuple[dict[str, object], ...] = (
        {"question": ""},
        {"question": "   "},
        {"pass_criterion": ""},
        {"pass_criterion": "   "},
        {"proposed_by": "   "},
        {"state": "proposed"},
        {"state": "confirmed"},
        {"state": "confirmed", "confirmed_by": "the-advisor"},
        {"state": "confirmed", "confirmed_by": "", "confirmed_at": LATER},
        {"state": "candidate", "confirmed_by": "the-advisor"},
        {"state": "withdrawn"},
        {"state": "withdrawn", "resolution_reason": "   "},
        {"state": "candidate", "resolution_reason": "a reason on a live check"},
    )
    for overrides in refusals:
        session = env.new_session()
        try:
            try:
                _raw_insert_check(session, **overrides)
            except IntegrityError:
                pass
            else:
                pytest.fail(f"the schema accepted a check row it must refuse: {overrides}")
        finally:
            session.rollback()
            session.close()


def _raw_rule(session: Session, rule_id: str = "rule-bound", version: int = 1) -> None:
    """Write the rule row a binding needs, so the check's key is what refuses."""
    session.add(
        GuidanceRuleRow(
            rule_id=rule_id,
            version=version,
            issue_type="method_and_hypothesis",
            statement="The advisor asks for the baseline to be named.",
            context="A results section whose claim is comparative.",
            scope="Empirical papers.",
            example="The comment of 2026-03-02.",
            state="candidate",
            proposed_by="distil-run-7",
            proposed_at=MOMENT,
        )
    )
    session.flush()


def _raw_check(session: Session, check_id: str = "check-bound") -> None:
    """Write the check row a binding needs, so the rule's key is what refuses."""
    session.add(
        GuidanceCheckRow(
            check_id=check_id,
            question="Does every comparison name what it compares against?",
            pass_criterion="The paragraph names the quantity compared against.",
            state="confirmed",
            proposed_by="the-group",
            proposed_at=MOMENT,
            confirmed_by="the-advisor",
            confirmed_at=LATER,
        )
    )
    session.flush()


def test_the_schema_refuses_a_binding_to_a_check_that_is_not_there(env: StoreEnv) -> None:
    """A rule may not name a check that does not exist.

    **The rule is there and the check is not**, so the only thing that can
    refuse the binding is the binding's own key on the check. **A witness
    that cannot say which key refused catches a different thing**, which is
    why the other half is written as its own witness.
    """
    session = env.new_session()
    try:
        _raw_rule(session)
        assert session.get(GuidanceCheckRow, "check-nowhere") is None, (
            "the check this binding names is there, so the refusal would be about something else"
        )
        try:
            session.add(
                GuidanceRuleCheckRow(rule_id="rule-bound", version=1, check_id="check-nowhere")
            )
            session.flush()
        except IntegrityError:
            pass
        else:
            pytest.fail("the schema accepted a binding to a check that does not exist")
    finally:
        session.rollback()
        session.close()


def test_the_schema_refuses_a_binding_to_a_rule_version_that_is_not_there(
    env: StoreEnv,
) -> None:
    """A check may not be bound to a version of a rule that does not exist.

    **The check is there and the rule version is not**, so the only thing
    that can refuse the binding is the binding's own key on the rule.
    """
    session = env.new_session()
    try:
        _raw_check(session)
        assert session.get(GuidanceRuleRow, ("rule-bound", 1)) is None, (
            "the rule version this binding names is there, so the refusal would be"
            " about something else"
        )
        try:
            session.add(
                GuidanceRuleCheckRow(rule_id="rule-bound", version=1, check_id="check-bound")
            )
            session.flush()
        except IntegrityError:
            pass
        else:
            pytest.fail("the schema accepted a binding to a rule version that does not exist")
    finally:
        session.rollback()
        session.close()
