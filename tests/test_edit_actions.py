"""The edit: a change made in answer to a comment, and **who made it**.

**What is under test.** LC-P2-09 T02: ``edit_actions``, and the
acceptance clause that carries it.

======  ================================================================
A6      an edit names who made it, and a model's change is not the
        advisor's
======  ================================================================

**Why the schema's refusals are witnessed by writing rows.** The
project's lesson from revision 0007: *"the parity test passed through it,
because the migration and the ORM were mangled identically — a test
comparing two texts cannot catch both being wrong."* So each rule is
witnessed by **writing a row the schema must refuse** and watching the
database refuse it, with a raw ``INSERT`` that bypasses the ORM.

**And the rule the table exists for.** ADR-0016 names *model → accepted
change* as the third of its three promotion paths: a model rewrites the
manuscript, the change is recorded, and it is attributed to the advisor.
The schema would be satisfied, the report would cite an address, and
**nothing would say the sentence was invented.** The ``actor_kind``
column is what makes that impossible to write by accident.
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
from labcairn.db.models import EditActionRow
from labcairn.papers.edits import list_edit_actions, record_edit
from labcairn.papers.feedback import record_feedback

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture()
def chain(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A workspace with one manuscript, one comment and one project."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(env.store(), workspace, comments=(a_comment("201"),))
    record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    return built


def _raw_insert(session: Session, **overrides: object) -> None:
    """Write an edit row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "edit_action_id": "ea-raw",
        "feedback_id": None,
        "version_edge_id": "edge-1",
        "actor_kind": "student",
        "actor_id": "student-1",
        "grade": "observed",
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO edit_actions ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


# --------------------------------------------------------------------------- #
# A6 — who made the change
# --------------------------------------------------------------------------- #


def test_an_edit_names_who_made_it(chain: ChainEnv) -> None:
    """An edit names who made it, and **a model's change is not the
    advisor's**.

    **Three rows, three actors, three records.** A change the student
    made is the student's; a change a model made is the model's; a change
    the advisor made is the advisor's. **The column is the whole point**,
    and a row that says ``advisor`` for a model's edit is a forged
    signature.

    **And there is no default actor**, because a default is how a model's
    change becomes the advisor's: the schema refuses a row that names no
    actor at all.
    """
    feedback = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )[0]

    student = record_edit(
        chain.context,
        edit_action_id="ea-student",
        version_edge_id=chain.edge_id,
        feedback_id=feedback.feedback_id,
        actor_kind="student",
        actor_id="student-1",
        now=MOMENT,
    )
    model = record_edit(
        chain.context,
        edit_action_id="ea-model",
        version_edge_id=chain.edge_id,
        feedback_id=feedback.feedback_id,
        actor_kind="model",
        now=MOMENT,
    )
    advisor = record_edit(
        chain.context,
        edit_action_id="ea-advisor",
        version_edge_id=chain.edge_id,
        feedback_id=feedback.feedback_id,
        actor_kind="advisor",
        actor_id="Prof. Lin",
        now=MOMENT,
    )

    assert student.actor_kind == "student"
    assert model.actor_kind == "model", "a model's change is recorded as the model's"
    assert advisor.actor_kind == "advisor"
    assert model.actor_id is None, "a model is not a person and carries no person's id"

    listed = list_edit_actions(chain.context, feedback_id=feedback.feedback_id)
    assert {action.edit_action_id for action in listed} == {
        "ea-student",
        "ea-model",
        "ea-advisor",
    }


def test_a_change_that_answers_nothing_is_not_an_error(chain: ChainEnv) -> None:
    """A student may edit for reasons the advisor never wrote down.

    **So ``feedback_id`` is nullable**, and a change that names no
    comment is a change the chain records rather than one it refuses.
    """
    recorded = record_edit(
        chain.context,
        edit_action_id="ea-alone",
        version_edge_id=chain.edge_id,
        feedback_id=None,
        actor_kind="student",
        actor_id="student-1",
        now=MOMENT,
    )

    assert recorded.feedback_id is None
    row = chain.context.store.session.get(EditActionRow, "ea-alone")
    assert row is not None
    assert row.feedback_id is None


# --------------------------------------------------------------------------- #
# the schema refuses
# --------------------------------------------------------------------------- #


def test_a_model_may_not_carry_a_persons_id(chain: ChainEnv) -> None:
    """A model's row may not name a person.

    **The absence of an id on a model's row is not an error** — that is
    what a model's change looks like — and the two are told apart by the
    schema rather than by the application layer's discretion.

    **What breaks it:** a constraint that let a ``model`` row carry an
    ``actor_id``, which is a forged signature written by accident.
    """
    session = chain.context.store.session

    with pytest.raises(IntegrityError):
        _raw_insert(session, edit_action_id="ea-forged", actor_kind="model", actor_id="Prof. Lin")
    session.rollback()


def test_an_actor_outside_the_vocabulary_is_refused(chain: ChainEnv) -> None:
    """A kind outside the four is a change nobody made.

    **And there is no default.** A row that names no actor at all is
    refused, because a default is how a model's change becomes the
    advisor's.
    """
    session = chain.context.store.session

    with pytest.raises(IntegrityError):
        _raw_insert(session, edit_action_id="ea-unknown", actor_kind="robot")
    session.rollback()

    with pytest.raises(IntegrityError):
        _raw_insert(session, edit_action_id="ea-no-actor", actor_kind=None)
    session.rollback()

    with pytest.raises(IntegrityError):
        _raw_insert(session, edit_action_id="ea-empty-actor", actor_kind="")
    session.rollback()


def test_the_operation_refuses_an_actor_outside_the_vocabulary(chain: ChainEnv) -> None:
    """The operation refuses it too, and says why.

    **A refusal rather than a constraint error.** The schema's refusal
    arrives as an integrity error in the middle of a write; this one
    arrives before the write, with a message that names what was wrong.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        record_edit(
            chain.context,
            edit_action_id="ea-robot",
            version_edge_id=chain.edge_id,
            actor_kind="robot",
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID


def test_the_operation_refuses_a_model_carrying_a_persons_id(chain: ChainEnv) -> None:
    """A model's change wearing somebody's name is refused before it is
    written.

    **The same forgery the schema refuses**, caught where the mistake was
    made rather than in the middle of the transaction.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        record_edit(
            chain.context,
            edit_action_id="ea-forged",
            version_edge_id=chain.edge_id,
            actor_kind="model",
            actor_id="Prof. Lin",
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID


def test_an_edit_names_the_edge_it_moved(chain: ChainEnv) -> None:
    """An edit names the edge it is — the parent/child pair it moved.

    **And an edge that cannot exist is a reference to nothing**, so the
    schema's foreign key refuses one.
    """
    session = chain.context.store.session

    with pytest.raises(IntegrityError):
        _raw_insert(session, edit_action_id="ea-no-edge", version_edge_id="edge-nope")
    session.rollback()

    with pytest.raises(ApplicationRefusedError) as caught:
        record_edit(
            chain.context,
            edit_action_id="ea-no-edge",
            version_edge_id="edge-nope",
            actor_kind="student",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_VERSION_NOT_FOUND


def test_a_grade_outside_the_vocabulary_is_refused(chain: ChainEnv) -> None:
    """A grade outside ADR-0014 D2's three levels says nothing about how
    the change is known.

    **So the schema refuses it**, and a row that could hold any string
    would be a row that carries no information.
    """
    session = chain.context.store.session
    with pytest.raises(IntegrityError):
        _raw_insert(session, edit_action_id="ea-bad-grade", grade="probably")
    session.rollback()
