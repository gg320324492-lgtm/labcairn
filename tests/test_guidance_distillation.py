"""The distillation: a model proposes, a person confirms, nobody invents a scope.

**What is under test.** LC-P2-11 T01's model half: ``distil_candidate``
and the three properties the work order names for it.

=====================================================  =========================
A7  a distilled rule is a **candidate** until a person  the creator is
    confirms it                                        ``model_proposal``,
                                                       and the proposer
                                                       cannot confirm their
                                                       own rule
A8  a suggestion does not become an advisor's rule by  retrieval has no
    being retrieved often                              side effects
A9  a rule whose scope the cases do not support is     the scope is the
    refused                                            cases', or there is
                                                       no rule
=====================================================  =========================
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import a_comment, build_chain
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.db.models import GuidanceRuleRow
from labcairn.guidance.distil import MODEL_PROPOSER, distil_candidate
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.guidance.retrieval import search_rules
from labcairn.guidance.rules import confirm_rule, read_rule
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)

KEY = "iss-gold-a-r1"

STATEMENT = (
    "When the claim rests on a comparison, the advisor asks for the baseline"
    " to be named in the same paragraph."
)


def allow_all() -> PermissionPolicy:
    """A policy that permits everything, for a test about something else."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _refusal(error: ApplicationRefusedError) -> GuidanceRefusal:
    return GuidanceRefusal(error.reason.value.removeprefix("guidance_"))


@pytest.fixture()
def cases(env: StoreEnv, tmp_path: Path) -> tuple[ApplicationContext, str]:
    """A chain with one judged comment under one key: a case to distil from.

    **No judgement rows** — the distillation reads the case, not the
    verdict on what was done about it; whether the change answered the
    comment is the retrieval's question, asked at serve time.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(
        store,
        workspace_root,
        comments=(a_comment("201"),),
    )
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    set_issue_key(chain.context, feedback_id=events[0].feedback_id, issue_key=KEY, now=MOMENT)
    return chain.context, chain.project_id


def _distil(context: ApplicationContext, **overrides: object):
    kwargs: dict[str, object] = {
        "issue_type": "method_and_hypothesis",
        "statement": STATEMENT,
        "rule_context": "A results section whose claim is comparative.",
        "issue_keys": (KEY,),
        "now": MOMENT,
    }
    kwargs.update(overrides)
    return distil_candidate(context, **kwargs)  # type: ignore[arg-type]


def test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it(
    cases: tuple[ApplicationContext, str],
) -> None:
    """A7: the creator is ``model_proposal``, and a person's word moves the state.

    **And the second-reader rule holds for a model's proposal too** —
    ``model_proposal`` is a proposer like any other, so the model cannot
    confirm its own work by any name.
    """
    context, _ = cases
    distilled = _distil(context)
    assert distilled.state == "candidate"
    assert distilled.proposed_by == MODEL_PROPOSER
    assert distilled.confirmed_by is None

    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(context, rule_id=distilled.rule_id, confirmed_by=MODEL_PROPOSER, now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER

    confirmed = confirm_rule(
        context, rule_id=distilled.rule_id, confirmed_by="the-advisor", now=LATER
    )
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_by == "the-advisor"
    assert confirmed.confirmed_at == LATER


def test_a_frequently_retrieved_suggestion_is_still_a_candidate(
    cases: tuple[ApplicationContext, str],
) -> None:
    """A8: retrieval has no side effects, so no amount of it promotes anything.

    **D9 in one query loop**: five retrievals of the suggestion leave the
    row's state where it was, and leave the store holding no more rows
    than it did — a suggestion does not become an advisor's rule by
    being retrieved often, because nothing about retrieval writes
    anything down.
    """
    context, _ = cases
    distilled = _distil(context)
    before = context.store.session.query(GuidanceRuleRow).count()
    for _ in range(5):
        served = search_rules(context, include_candidates=True)
    assert [hit.rule.rule_id for hit in served] == [distilled.rule_id]
    after = context.store.session.query(GuidanceRuleRow).count()
    assert after == before, "retrieval wrote something, and a write is a promotion path"
    assert read_rule(context, rule_id=distilled.rule_id).state == "candidate"


def test_a_rule_with_an_unsupported_scope_is_refused(
    cases: tuple[ApplicationContext, str],
) -> None:
    """A9: the scope is the cases', or there is no rule.

    **No cases, no scope, no rule** — an empty case list is refused. A
    case the chain cannot show is refused by name. And a distilled
    rule's scope is the anchored text the cases were written against:
    the caller had no parameter to write it with, and the assembled
    scope says where it came from.
    """
    context, _ = cases

    with pytest.raises(ApplicationRefusedError) as raised:
        _distil(context, issue_keys=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE

    with pytest.raises(ApplicationRefusedError) as raised:
        _distil(context, issue_keys=("iss-nowhere",))
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE
    assert "iss-nowhere" in str(raised.value)

    distilled = _distil(context)
    assert distilled.scope == (
        'Cases whose anchored text reads: "The method estimates the parameter'
        ' from a single observation."'
    ), "the scope is the case's anchored text, assembled, not a caller's words"
    assert distilled.example.startswith("The advisor's comment (iss-gold-a-r1):")
    assert "Define the parameter." in distilled.example
