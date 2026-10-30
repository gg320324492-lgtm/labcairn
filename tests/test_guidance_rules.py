"""The guidance memory: a rule that carries its sources, and the second reader.

**What is under test.** LC-P2-11 T00 and T01: ``guidance_rules``, its
sources and its counterexamples, and the lifecycle API that proposes,
confirms, disputes, withdraws and supersedes.

======================================================  =========================
A1   a rule is a row                                     every field the work
                                                          order lists, plus its
                                                          sources and its cases
A2   the problem is from the vocabulary                  a label outside the
                                                          thirteen is refused
A3   a rule without a source is not a rule               the API refuses it, and
                                                          the schema would too
A4   the work order's "must not" row                     an empty field is
                                                          refused by API and by
                                                          schema
A5   the state machine is closed                         an illegal state is
                                                          refused by the database
A6   a confirmed rule names its confirmer                the database refuses a
                                                          confirmation without a
                                                          name
A7   **the confirmer is a second reader**                the proposer confirming
                                                          their own rule is
                                                          refused, and a second
                                                          reader's confirmation
                                                          lands
A8   a dispute and a retraction carry their reason       a shrug is refused
A9   a new statement is a new row                        the old version keeps
                                                          its state; the new one
                                                          is a candidate again
A10  a counterexample travels with the rule              served in the same read,
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
from labcairn.db.models import GuidanceRuleRow
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
    )


def _refusal(call: object) -> GuidanceRefusal:
    """The guidance refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return GuidanceRefusal(call.reason.value.removeprefix("guidance_"))


def test_a_rule_is_a_row_that_carries_every_field(memory: ApplicationContext) -> None:
    """A1: a rule is a row carrying every field, its sources and its cases.

    **The cases are an empty tuple, not a null.** A rule proposed before
    anybody challenged it has no counterexamples, and the read still
    carries the collection — an empty tuple says the memory holds none,
    not that it did not look.
    """
    rule = _propose(memory, sources=("iss-gold-a-r1", "iss-gold-a-r2"))
    read_back = read_rule(memory, rule_id=rule.rule_id)
    assert read_back.state == "candidate"
    assert read_back.version == 1
    assert read_back.issue_type == "method_and_hypothesis"
    assert read_back.proposed_by == "distil-run-7"
    assert read_back.confirmed_by is None
    assert read_back.confirmed_at is None
    assert read_back.resolution_reason is None
    assert read_back.sources == ("iss-gold-a-r1", "iss-gold-a-r2")
    assert read_back.counterexamples == ()


def test_a_problem_outside_the_vocabulary_is_refused(
    memory: ApplicationContext,
) -> None:
    """A2: a label outside the thirteen is refused, at the boundary with a name."""
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose(memory, issue_type="advisor_preference")
    assert _refusal(raised.value) is GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY, raised.value


def test_a_rule_without_a_source_is_refused(memory: ApplicationContext) -> None:
    """A3: a rule that names no chain material is not stored.

    **The database cannot count a rule's sources** — a cross-table CHECK
    is not SQLite's to give — so this is the API's refusal, and the
    witness for the schema's half is that the schema holds the rows the
    API does write.
    """
    with pytest.raises(ApplicationRefusedError) as raised:
        _propose(memory, sources=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE, raised.value


def test_an_empty_field_is_refused(memory: ApplicationContext) -> None:
    """A4: the work order's "must not" row — a rule with nothing in it."""
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
    session.add(GuidanceRuleRow(**values))  # type: ignore[arg-type]
    session.flush()


def test_the_schema_refuses_what_the_api_refuses(env: StoreEnv) -> None:
    """A4-A6 at the schema: the rows the database itself must refuse.

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
    """A7: the second-reader rule, as the owner wrote it on 2026-10-31.

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
    """A7, the other way: a different person's confirmation lands."""
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
    """A8: a shrug is refused, in both of the resolution's forms."""
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
    """A9: the memory does not edit its past.

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
    """A10: the case against the rule comes back in the same read.

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
