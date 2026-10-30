"""The response: the judgement that a change answered a comment, and its
evidence.

**What is under test.** LC-P2-09 T03: ``response_links``, and the four
acceptance clauses that carry it.

======  ================================================================
A7      a response's state cannot be reached without a decision and its
        evidence
A8      a comment with no response is **listed as unaddressed**
A9      a change that does not answer the comment is recorded as
        ``not_addressed`` and **exists**
A10     a partly-answering change is ``partially_addressed`` and not
        ``addressed``
======  ================================================================

**Why the schema's refusals are witnessed by writing rows.** The
project's lesson from revision 0007: *"the parity test passed through it,
because the migration and the ORM were mangled identically — a test
comparing two texts cannot catch both being wrong."* So each rule is
witnessed by **writing a row the schema must refuse** and watching the
database refuse it, with a raw ``INSERT`` that bypasses the ORM.

**And the clause this table exists for.** *"An unaddressed comment is
not reported as addressed, and neither is a wrong response or a partial
one."*
"""

from __future__ import annotations

from pathlib import Path

import pytest
from feedback_chain_fixtures import MOMENT, ChainEnv, a_comment, build_chain
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.papers.edits import record_edit
from labcairn.papers.feedback import record_feedback
from labcairn.papers.responses import list_response_links, list_unaddressed, record_response

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture()
def chain(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A workspace with one manuscript, one comment, one change."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(env.store(), workspace, comments=(a_comment("201"),))
    feedback = record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )[0]
    record_edit(
        built.context,
        edit_action_id="ea-1",
        version_edge_id=built.edge_id,
        feedback_id=feedback.feedback_id,
        actor_kind="student",
        actor_id="student-1",
        now=MOMENT,
    )
    return built


def _feedback_id(chain: ChainEnv) -> str:
    return record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )[0].feedback_id


def _raw_insert(session: Session, **overrides: object) -> None:
    """Write a response row directly, so the schema is what is under test.

    **The evidence is written as JSON text**, because a raw ``INSERT``
    carries no type information and a Python list is not a value SQLite
    can bind. The column's own type does the rest.
    """
    values: dict[str, object] = {
        "response_link_id": "rl-raw",
        "feedback_id": "fb-whatever",
        "edit_action_id": "ea-1",
        "state": "pending",
        "grade": "observed",
        "decided_by": None,
        "decided_at": None,
        "evidence_refs": "[]",
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO response_links ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


# --------------------------------------------------------------------------- #
# A7 — a state cannot be reached without a decision and its evidence
# --------------------------------------------------------------------------- #


def test_a_response_state_needs_a_decision_and_its_evidence(chain: ChainEnv) -> None:
    """A state other than ``pending`` needs a decider and the evidence.

    **A status anybody can set is not a status**, so the schema refuses a
    judgement with no evidence behind it — and so does the operation,
    which refuses it before the write with a message that names what was
    missing.

    **What breaks it:** a constraint that let ``state='addressed'`` through
    with no ``evidence_refs``, or an operation that filled the gap with a
    default.
    """
    session = chain.context.store.session
    feedback_id = _feedback_id(chain)

    # The schema refuses it: a decided link with no evidence.
    with pytest.raises(IntegrityError):
        _raw_insert(
            session,
            response_link_id="rl-no-evidence",
            feedback_id=feedback_id,
            state="addressed",
            decided_by="user",
            decided_at="2026-04-01T09:00:00+00:00",
            evidence_refs="[]",
        )
    session.rollback()

    # The schema refuses it: a decided link with no decider.
    with pytest.raises(IntegrityError):
        _raw_insert(
            session,
            response_link_id="rl-no-decider",
            feedback_id=feedback_id,
            state="addressed",
            decided_by=None,
            decided_at="2026-04-01T09:00:00+00:00",
            evidence_refs='["evidence:1"]',
        )
    session.rollback()

    # The schema refuses it: a decided link with no moment.
    with pytest.raises(IntegrityError):
        _raw_insert(
            session,
            response_link_id="rl-no-moment",
            feedback_id=feedback_id,
            state="addressed",
            decided_by="user",
            decided_at=None,
            evidence_refs='["evidence:1"]',
        )
    session.rollback()

    # And the operation refuses it too.
    with pytest.raises(ApplicationRefusedError) as caught:
        record_response(
            chain.context,
            response_link_id="rl-no-evidence",
            feedback_id=feedback_id,
            edit_action_id="ea-1",
            state="addressed",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_RESPONSE_NEEDS_EVIDENCE

    # And a pending link may hold no decision at all.
    pending = record_response(
        chain.context,
        response_link_id="rl-pending",
        feedback_id=feedback_id,
        edit_action_id="ea-1",
        state="pending",
        now=MOMENT,
    )
    assert pending.decided_by is None
    assert pending.decided_at is None
    assert pending.evidence_refs == ()


def test_a_model_may_put_a_link_forward_but_not_decide_one(chain: ChainEnv) -> None:
    """A model's link is a *candidate*, and a candidate is not a decision.

    **The acceptance of a change is not an answer.** A link is
    ``addressed`` only when a rule or a person says so, and the thing that
    said so is on the row. A model may propose the association — that is
    what ADR-0016's promotion path is — but it may not settle it.

    **What breaks it:** a schema or an operation that lets ``decided_by``
    be ``model`` on a decided row.
    """
    session = chain.context.store.session
    feedback_id = _feedback_id(chain)

    with pytest.raises(IntegrityError):
        _raw_insert(
            session,
            response_link_id="rl-model-decided",
            feedback_id=feedback_id,
            state="addressed",
            decided_by="model",
            decided_at="2026-04-01T09:00:00+00:00",
            evidence_refs='["model:1"]',
            grade="inferred",
        )
    session.rollback()

    with pytest.raises(ApplicationRefusedError) as caught:
        record_response(
            chain.context,
            response_link_id="rl-model-decided",
            feedback_id=feedback_id,
            edit_action_id="ea-1",
            state="addressed",
            grade="inferred",
            decided_by="model",
            decided_at=MOMENT,
            evidence_refs=("model:1",),
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_RESPONSE_MAY_NOT_BE_DECIDED_BY_A_MODEL

    # And a model's candidate is a pending link at grade 'inferred'.
    candidate = record_response(
        chain.context,
        response_link_id="rl-candidate",
        feedback_id=feedback_id,
        edit_action_id="ea-1",
        state="pending",
        grade="inferred",
        decided_by="model",
        now=MOMENT,
    )
    assert candidate.state == "pending"
    assert candidate.grade == "inferred"
    assert candidate.decided_by == "model"
    assert candidate.evidence_refs == ()


def test_a_state_outside_the_vocabulary_is_refused(chain: ChainEnv) -> None:
    """A state outside the four says nothing about whether the comment
    was answered.
    """
    session = chain.context.store.session
    feedback_id = _feedback_id(chain)

    with pytest.raises(IntegrityError):
        _raw_insert(
            session,
            response_link_id="rl-bad-state",
            feedback_id=feedback_id,
            state="mostly_addressed",
        )
    session.rollback()

    with pytest.raises(ApplicationRefusedError) as caught:
        record_response(
            chain.context,
            response_link_id="rl-bad-state",
            feedback_id=feedback_id,
            edit_action_id="ea-1",
            state="mostly_addressed",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID


# --------------------------------------------------------------------------- #
# A8 — a comment with no response is listed as unaddressed
# --------------------------------------------------------------------------- #


def test_an_unanswered_comment_is_listed_as_unaddressed(chain: ChainEnv) -> None:
    """A comment with no response is **on the listing**, and it is
    unaddressed.

    **Not absent from it.** A listing that omitted it would make the
    chain's silence indistinguishable from its having nothing to say, and
    the reader asking "what has not been dealt with?" would get an empty
    answer that looks like "nothing is outstanding".

    **And a comment that has been answered is not on it.**
    """
    feedback_id = _feedback_id(chain)

    unaddressed = list_unaddressed(chain.context, project_id=chain.project_id)
    assert [item.feedback.feedback_id for item in unaddressed] == [feedback_id]
    assert unaddressed[0].reason == "no_response"

    record_response(
        chain.context,
        response_link_id="rl-addressed",
        feedback_id=feedback_id,
        edit_action_id="ea-1",
        state="addressed",
        decided_by="user",
        decided_at=MOMENT,
        evidence_refs=("attestation:1",),
        now=MOMENT,
    )

    assert list_unaddressed(chain.context, project_id=chain.project_id) == ()


# --------------------------------------------------------------------------- #
# A9 — a change that does not answer
# --------------------------------------------------------------------------- #


def test_a_change_that_does_not_answer_is_recorded_as_not_addressed(chain: ChainEnv) -> None:
    """A change that does not answer the comment is ``not_addressed``, and
    **it exists**.

    **The student did something, and the record says it did not help.**
    A chain that only knew about "answered" would have to either hide
    those changes or call them successes, and both are false.

    **And the comment is still on the unaddressed listing** — a link that
    says "not addressed" is not an answer.
    """
    feedback_id = _feedback_id(chain)

    link = record_response(
        chain.context,
        response_link_id="rl-not-addressed",
        feedback_id=feedback_id,
        edit_action_id="ea-1",
        state="not_addressed",
        decided_by="rule",
        decided_at=MOMENT,
        evidence_refs=("rule:no-overlap",),
        now=MOMENT,
    )

    assert link.state == "not_addressed"
    assert link.evidence_refs == ("rule:no-overlap",), "the evidence is on the row"

    listed = list_response_links(chain.context, feedback_id=feedback_id)
    assert [item.response_link_id for item in listed] == ["rl-not-addressed"]

    unaddressed = list_unaddressed(chain.context, project_id=chain.project_id)
    assert [item.feedback.feedback_id for item in unaddressed] == [feedback_id]
    assert unaddressed[0].reason == "not_addressed"


# --------------------------------------------------------------------------- #
# A10 — a partial answer is not an answer
# --------------------------------------------------------------------------- #


def test_a_partial_answer_is_not_an_answer(chain: ChainEnv) -> None:
    """A partly-answering change is ``partially_addressed`` and **not**
    ``addressed``.

    **The two are different claims.** ``partially_addressed`` says it
    helped with part; ``addressed`` says the comment was answered. A
    partly-answered comment is still on the unaddressed listing.
    """
    feedback_id = _feedback_id(chain)

    link = record_response(
        chain.context,
        response_link_id="rl-partial",
        feedback_id=feedback_id,
        edit_action_id="ea-1",
        state="partially_addressed",
        decided_by="rule",
        decided_at=MOMENT,
        evidence_refs=("rule:partial-overlap",),
        now=MOMENT,
    )

    assert link.state == "partially_addressed"
    assert link.state != "addressed"

    unaddressed = list_unaddressed(chain.context, project_id=chain.project_id)
    assert [item.feedback.feedback_id for item in unaddressed] == [feedback_id]
    assert unaddressed[0].reason == "partially_addressed"
