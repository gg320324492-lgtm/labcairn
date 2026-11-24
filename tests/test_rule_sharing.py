"""A confirmed rule may be shared with the group, or kept private.

**What is under test.** Phase 4 §8.5 / P4-G3: the mentor's confirmed rules
become the whole research group's working rules. A rule a second reader
confirmed may be *published to the group* — served to every project's
retrieval — and retracted again, and the sharing travels beside the rule's
own state machine without touching it.

======================================================  =========================
the sharing is a scope, not a state                     ``shared_scope`` is
                                                        ``private`` or
                                                        ``group``; a rule the
                                                        group may not see is
                                                        still the rule its own
                                                        project cites
only a confirmed rule is published                      a candidate, a disputed
                                                        rule and a withdrawn
                                                        rule are each refused
**the publisher is a second reader**                    the proposer publishing
                                                        their own rule is
                                                        refused, and a second
                                                        reader's publication
                                                        lands
a publication names its publisher and moment            the retrieval can say
                                                        who shared the rule,
                                                        and when
**a project sees its rules and the group's**            a rule learned in
                                                        another project is not
                                                        served until it is
                                                        published; once
                                                        published it is; once
                                                        retracted it is not
the state machine is untouched by the sharing           a published rule keeps
                                                        its state; a retracted
                                                        sharing keeps the
                                                        rule's state
the sources' permission is still asked at serve time    a shared rule whose
                                                        source a reader cannot
                                                        reach is not served to
                                                        them
the schema holds the sharing closed                     the vocabulary and the
                                                        publication's fields
                                                        are constrained; the
                                                        migration builds and
                                                        unbuilds them
======================================================  =========================

**Why the chain rows are real.** The same reason
``tests/test_guidance_retrieval.py`` gives: the retrieval resolves a rule's
sources against the chain's *current* state, and only real chain rows make
that resolution mean anything. The fixture is the retrieval tests' own —
two judged comments under keys a rule cites — plus a **second project**
whose chain holds nothing the first project's rule was learned from, which
is what makes "another project" a fact about the rows and not a wish.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.application.guidance import read_guidance_rule
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.models import PaperProjectRow
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.retrieval import search_rules
from labcairn.guidance.rules import (
    confirm_rule,
    propose_rule,
    publish_rule_to_group,
    retract_rule_from_group,
)

pytestmark = pytest.mark.integration

#: pytest resolves a fixture by the parameter name in a test's signature, so
#: the shared ``env`` fixture must be bound under that name here. Importing it
#: directly and taking ``env`` as a parameter would make every signature below
#: an F811 redefinition; aliasing the import and rebinding it keeps both.
env = _shared_env

#: The one moment the chain's tests write. **No wall clock**, for the
#: project's reason.
MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
AFTER = datetime(2026, 4, 3, 9, 0, tzinfo=UTC)

KEY_ONE = "iss-gold-a-r1"
KEY_TWO = "iss-gold-b-r2"

BASELINE = "State the parameter's definition before the claim that uses it."

#: The mentor who confirms and publishes — never the proposer.
MENTOR = "the-advisor"
#: The person whose rules these are: the proposer, who may not publish
#: their own rule.
PROPOSER = "the-student"


@pytest.fixture()
def chain(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A first project's chain: two judged comments, keys ready.

    **The keys and the judgements are written the way the retrieval tests
    write them.** The rule cites ``KEY_ONE``; the feedback event that
    carries it is keyed, and the response link judges the change
    ``addressed`` — so the source *lives*, and the project it belongs to
    is a fact the chain's rows carry.
    """
    from labcairn.db.models import EditActionRow, ResponseLinkRow
    from labcairn.papers.feedback import record_feedback, set_issue_key

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    built = build_chain(store, workspace_root, comments=(a_comment("201"), a_comment("202")))
    events = record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    session = built.context.store.session
    for event, key in zip(events, (KEY_ONE, KEY_TWO), strict=True):
        edit_action_id = f"edit-{event.feedback_id[-6:]}"
        session.add(
            EditActionRow(
                edit_action_id=edit_action_id,
                feedback_id=event.feedback_id,
                version_edge_id=built.edge_id,
                actor_kind="student",
                grade="observed",
                created_at=MOMENT,
            )
        )
        session.add(
            ResponseLinkRow(
                response_link_id=f"resp-{key[-2:]}",
                feedback_id=event.feedback_id,
                edit_action_id=edit_action_id,
                state="addressed",
                grade="human_verified",
                decided_by="user",
                decided_at=LATER,
                evidence_refs=[f"check:{key}"],
                created_at=LATER,
            )
        )
        set_issue_key(built.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
    session.flush()
    return built


@pytest.fixture()
def context(chain: ChainEnv) -> ApplicationContext:
    """The first project's context, under an allowing policy."""
    return chain.context


def _second_project(context: ApplicationContext, project_id: str) -> None:
    """A second project in the same workspace, with no chain of its own.

    **A project is a row, not a wish.** The retrieval's project scoping is
    a fact about which projects the chain's rows name, so the second
    project is written the way the product writes one — and it holds no
    feedback events, so nothing is shared with it by accident. The write
    commits, so a service request that follows is not blocked by the
    test's own transaction.
    """
    session = context.store.session
    session.add(
        PaperProjectRow(
            project_id=project_id,
            workspace_id="ws-2",
            subject_pseudonym="subject-2",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    session.commit()


def _propose(context: ApplicationContext, *, proposed_by: str = PROPOSER) -> GuidanceRule:
    """A candidate over the first project's first source.

    **The write is flushed and committed by the caller that needs the row
    to be in the store.** The layer's own writes flush; the commit is the
    unit of work's, and a caller that hands the row to a service request
    commits first (see :func:`_propose_over_api`).
    """
    return propose_rule(
        context,
        issue_type="method_and_hypothesis",
        statement=BASELINE,
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        sources=(KEY_ONE,),
        proposed_by=proposed_by,
        now=MOMENT,
    )


def _confirmed(context: ApplicationContext, *, proposed_by: str = PROPOSER) -> GuidanceRule:
    """A confirmed rule: proposed by one person, confirmed by a second."""
    rule = _propose(context, proposed_by=proposed_by)
    return confirm_rule(context, rule_id=rule.rule_id, confirmed_by=MENTOR, now=LATER)


# -- the sharing is a scope, not a state ------------------------------------- #


def test_a_rule_is_private_until_it_is_published(context: ApplicationContext) -> None:
    """A confirmed rule serves its own project, and no other, until published.

    **Private is the fact, not a wish**: the rule stands, it is served to
    the project it was learned in, and the second project's retrieval does
    not see it — because nothing has published it to the group.
    """
    rule = _confirmed(context)
    _second_project(context, "proj-2")
    assert rule.shared_scope == "private"
    assert rule.published_by is None and rule.published_at is None

    served_here = [hit.rule.rule_id for hit in search_rules(context, project_id="proj-1")]
    assert served_here == [rule.rule_id], "the rule's own project sees it"
    assert search_rules(context, project_id="proj-2") == (), (
        "another project does not see a private rule"
    )


def test_publishing_moves_the_scope_and_names_the_publisher(
    context: ApplicationContext,
) -> None:
    """A published rule is shared with the group, and the record says who and when.

    **The publication is the sharing.** The row's scope moves to
    ``group`` and carries the mentor's name and the moment — the facts the
    retrieval asks at serve time — and the rule's own state is untouched.
    """
    rule = _confirmed(context)
    published = publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    assert published.shared_scope == "group"
    assert published.published_by == MENTOR
    assert published.published_at == AFTER
    assert published.state == "confirmed", "the sharing does not move the state"


def test_retracting_the_sharing_keeps_the_rule_standing(
    context: ApplicationContext,
) -> None:
    """A retraction of the sharing is not a withdrawal of the rule.

    **The rule's own project keeps its rule.** The scope goes back to
    ``private``, the publication's name and moment are cleared, and the
    state stays what it was — the state machine's ``withdrawn`` is the
    word for *this stopped being true*, and a retraction of the sharing
    says only *this stopped being shared*.
    """
    rule = _confirmed(context)
    publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    retracted = retract_rule_from_group(context, rule_id=rule.rule_id)
    assert retracted.shared_scope == "private"
    assert retracted.published_by is None and retracted.published_at is None
    assert retracted.state == "confirmed"

    read_back = read_guidance_rule(context, rule_id=rule.rule_id)
    assert read_back.shared_scope == "private"
    assert read_back.state == "confirmed"


def test_retracting_a_sharing_that_is_not_there_is_refused(
    context: ApplicationContext,
) -> None:
    """A private rule has no sharing to retract.

    **A door that is not open cannot be closed.** The retraction refuses
    a rule whose scope is already private, by name — the same
    transition-not-possible refusal the state machine uses — rather than
    quietly doing nothing and reporting success.
    """
    rule = _confirmed(context)
    with pytest.raises(ApplicationRefusedError) as refused:
        retract_rule_from_group(context, rule_id=rule.rule_id)
    assert refused.value.reason is ApplicationRefusal.GUIDANCE_TRANSITION_NOT_POSSIBLE


def test_republishing_a_shared_rule_is_refused(context: ApplicationContext) -> None:
    """A rule already shared with the group is not published again.

    **A decision made twice is a decision nobody can date.** A second
    publication would overwrite the first mentor's name with the second's,
    so the layer refuses it rather than letting the record change hands.
    """
    rule = _confirmed(context)
    publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    with pytest.raises(ApplicationRefusedError) as refused:
        publish_rule_to_group(
            context, rule_id=rule.rule_id, published_by="another-mentor", now=AFTER
        )
    assert refused.value.reason is ApplicationRefusal.GUIDANCE_TRANSITION_NOT_POSSIBLE


# -- only a confirmed rule is published -------------------------------------- #


def test_a_candidate_is_not_published(context: ApplicationContext) -> None:
    """Unreviewed experience is not a rule the group may cite.

    **§8.5's hard line, at the group's door too.** A candidate reaching
    another project's card would be a proposal dressed as a record — the
    same refusal the memory already makes for a card, made again for the
    whole group.
    """
    rule = _propose(context)
    with pytest.raises(ApplicationRefusedError) as refused:
        publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    assert refused.value.reason is ApplicationRefusal.GUIDANCE_PUBLISH_NOT_CONFIRMED


def test_a_disputed_rule_is_not_published(context: ApplicationContext) -> None:
    """A rule that does not stand is not shared with the group.

    **A disputed rule carries its reason**, and the reason is the memory's
    word that the rule is contested. Sharing a contested rule with the
    group would serve the contest as if it were settled.
    """
    from labcairn.guidance.rules import dispute_rule

    rule = _confirmed(context)
    dispute_rule(
        context,
        rule_id=rule.rule_id,
        disputed_by=MENTOR,
        reason="the case does not hold",
        now=AFTER,
    )
    with pytest.raises(ApplicationRefusedError) as refused:
        publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    assert refused.value.reason is ApplicationRefusal.GUIDANCE_PUBLISH_NOT_CONFIRMED


def test_a_withdrawn_rule_is_not_published(context: ApplicationContext) -> None:
    """A rule the mentor has retracted is not shared with the group.

    **A withdrawn rule is out of force.** Publishing it would share a
    rule the memory has already stopped serving — the state machine's
    refusal, asked at the group's door.
    """
    from labcairn.guidance.rules import withdraw_rule

    rule = _confirmed(context)
    withdraw_rule(context, rule_id=rule.rule_id, reason="superseded by the new protocol", now=AFTER)
    with pytest.raises(ApplicationRefusedError) as refused:
        publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    assert refused.value.reason is ApplicationRefusal.GUIDANCE_PUBLISH_NOT_CONFIRMED


# -- the publisher is a second reader ---------------------------------------- #


def test_the_proposer_cannot_publish_their_own_rule(
    context: ApplicationContext,
) -> None:
    """Whoever proposed a rule cannot be the one who publishes it.

    **The second-reader rule, at the group's door.** One person reading
    twice is one person reading once with extra steps; a rule the whole
    group may cite is a rule somebody other than its proposer stood
    behind. The refusal is the memory's own, by name.
    """
    rule = _confirmed(context, proposed_by=PROPOSER)
    with pytest.raises(ApplicationRefusedError) as refused:
        publish_rule_to_group(context, rule_id=rule.rule_id, published_by=PROPOSER, now=AFTER)
    assert refused.value.reason is ApplicationRefusal.GUIDANCE_PUBLISHER_IS_PROPOSER


# -- a project sees its rules and the group's -------------------------------- #


def test_a_published_rule_is_served_to_another_project(
    context: ApplicationContext,
) -> None:
    """The group's retrieval serves a published rule to every project.

    **The share, then the serve.** Before publication the second project
    sees nothing; after it, the rule is served there — and to the project
    it was learned in, which never loses sight of its own rule.
    """
    rule = _confirmed(context)
    _second_project(context, "proj-2")
    assert search_rules(context, project_id="proj-2") == ()

    publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    assert [hit.rule.rule_id for hit in search_rules(context, project_id="proj-2")] == [
        rule.rule_id
    ]
    assert [hit.rule.rule_id for hit in search_rules(context, project_id="proj-1")] == [
        rule.rule_id
    ], "the rule's own project still sees it"
    assert [hit.rule.rule_id for hit in search_rules(context)] == [rule.rule_id], (
        "the workbench's own view — no project named — still sees it"
    )


def test_a_retracted_rule_is_not_served_to_another_project_any_more(
    context: ApplicationContext,
) -> None:
    """After a retraction the group's projects stop seeing the rule.

    **The retraction is a door closing, and the closure is the retrieval's
    to honour**: the next query the second project asks does not serve the
    rule, and the project it was learned in still does.
    """
    rule = _confirmed(context)
    _second_project(context, "proj-2")
    publish_rule_to_group(context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    assert len(search_rules(context, project_id="proj-2")) == 1

    retract_rule_from_group(context, rule_id=rule.rule_id)
    assert search_rules(context, project_id="proj-2") == ()
    assert [hit.rule.rule_id for hit in search_rules(context, project_id="proj-1")] == [
        rule.rule_id
    ], "the rule's own project keeps it"


def test_a_candidate_is_never_shared_even_when_a_second_project_asks(
    context: ApplicationContext,
) -> None:
    """A candidate is not published and not served across the boundary.

    **The scoping never widens what the state machine refuses.** A
    candidate in the asking project's own memory is served only when the
    caller asks for candidates explicitly — the retrieval's existing
    rule — and a candidate in another project is not served at all.
    """
    rule = _propose(context)
    _second_project(context, "proj-2")
    assert search_rules(context, project_id="proj-2", include_candidates=True) == ()
    assert [
        hit.rule.rule_id
        for hit in search_rules(context, project_id="proj-1", include_candidates=True)
    ] == [rule.rule_id], "the candidate is the asking project's own, shown to its reviewer only"
    assert rule.state == "candidate"


# -- the sources' permission is still asked at serve time --------------------- #


def test_a_shared_rule_is_not_served_to_a_reader_who_cannot_reach_its_source(
    env: StoreEnv, tmp_path: Path
) -> None:
    """Scope decides which rules are asked about; permission decides what is served.

    **The permission layer is not bypassed by the sharing.** A rule the
    group may cite is still served only where its source material may be
    read (ADR-0003 C5, unchanged): a reader whose policy denies the
    source is not served the rule, though the scoping would have
    answered with it. **A shared rule is a widening of who is *asked*,
    never of what is *shown*.**
    """
    from labcairn.security.capabilities import CapabilityId
    from labcairn.security.policy import Permission, PermissionPolicy, Rule

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    built = build_chain(store, workspace_root, comments=(a_comment("201"),))
    from labcairn.db.models import EditActionRow, ResponseLinkRow
    from labcairn.papers.feedback import record_feedback, set_issue_key

    events = record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    session = built.context.store.session
    for event, key in zip(events, (KEY_ONE,), strict=True):
        edit_action_id = f"edit-{event.feedback_id[-6:]}"
        session.add(
            EditActionRow(
                edit_action_id=edit_action_id,
                feedback_id=event.feedback_id,
                version_edge_id=built.edge_id,
                actor_kind="student",
                grade="observed",
                created_at=MOMENT,
            )
        )
        session.add(
            ResponseLinkRow(
                response_link_id=f"resp-{key[-2:]}",
                feedback_id=event.feedback_id,
                edit_action_id=edit_action_id,
                state="addressed",
                grade="human_verified",
                decided_by="user",
                decided_at=LATER,
                evidence_refs=[f"check:{key}"],
                created_at=LATER,
            )
        )
        set_issue_key(built.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
    session.flush()
    rule = propose_rule(
        built.context,
        issue_type="method_and_hypothesis",
        statement=BASELINE,
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        sources=(KEY_ONE,),
        proposed_by=PROPOSER,
        now=MOMENT,
    )
    confirm_rule(built.context, rule_id=rule.rule_id, confirmed_by=MENTOR, now=LATER)
    publish_rule_to_group(built.context, rule_id=rule.rule_id, published_by=MENTOR, now=AFTER)
    _second_project(built.context, "proj-2")

    denied = ApplicationContext(
        workspace=built.context.workspace,
        store=built.context.store,
        policy=PermissionPolicy.from_rules(
            [
                Rule(
                    effect=Permission.DENY,
                    pattern="**",
                    capabilities=frozenset({CapabilityId.SOURCE_READ.value}),
                )
            ]
        ),
        ledger=built.context.ledger,
    )
    assert search_rules(built.context, project_id="proj-2") != (), (
        "the allowing policy serves the shared rule"
    )
    assert search_rules(denied, project_id="proj-2") == (), (
        "a reader who cannot reach the source is not served the rule"
    )


# -- the schema holds the sharing closed -------------------------------------- #


def test_the_schema_refuses_a_sharing_outside_the_vocabulary(
    env: StoreEnv,
) -> None:
    """A scope outside ``private``/``group`` is refused by the database.

    **A word nobody can filter by is not a scope.** The CHECK the
    migration writes is the schema's own refusal, and it is asked the way
    the state machine's is — by trying to write the row.
    """
    import sqlalchemy as sa

    from labcairn.db.models import GuidanceRuleRow

    session = env.session
    row = GuidanceRuleRow(
        rule_id="rule-bad-scope",
        version=1,
        issue_type="method_and_hypothesis",
        statement=BASELINE,
        context="A results section.",
        scope="Empirical papers.",
        example="A comment.",
        state="confirmed",
        proposed_by=PROPOSER,
        proposed_at=MOMENT,
        confirmed_by=MENTOR,
        confirmed_at=MOMENT,
        shared_scope="everyone",
    )
    session.add(row)
    with pytest.raises(sa.exc.IntegrityError):
        session.flush()
    session.rollback()


def test_the_schema_refuses_a_sharing_without_its_publication(
    env: StoreEnv,
) -> None:
    """A rule shared with the group names its publisher and moment, or the
    database refuses it.

    **The publication is the sharing.** A row whose scope says ``group``
    but whose publisher or moment is missing is a sharing nobody made —
    the schema refuses it, the same way it refuses a confirmation without
    a confirmer.
    """
    import sqlalchemy as sa

    from labcairn.db.models import GuidanceRuleRow

    session = env.session
    for missing in ("published_by", "published_at"):
        row = GuidanceRuleRow(
            rule_id=f"rule-unnamed-{missing}",
            version=1,
            issue_type="method_and_hypothesis",
            statement=BASELINE,
            context="A results section.",
            scope="Empirical papers.",
            example="A comment.",
            state="confirmed",
            proposed_by=PROPOSER,
            proposed_at=MOMENT,
            confirmed_by=MENTOR,
            confirmed_at=MOMENT,
            shared_scope="group",
        )
        if missing == "published_by":
            row.published_by = None
            row.published_at = MOMENT
        else:
            row.published_by = MENTOR
            row.published_at = None
        session.add(row)
        with pytest.raises(sa.exc.IntegrityError):
            session.flush()
        session.rollback()


# -- the API doors ------------------------------------------------------------ #


@pytest.fixture()
def api(
    env: StoreEnv, tmp_path: Path
) -> Iterator[tuple[TestClient, dict[str, str], ApplicationContext, str]]:
    """The service over a chain, with its token, and the first project's id.

    **The same shape the other API witnesses use**: the app over a real
    context, the session token read the way a client reads it, and the
    Authorization header built from it. The rule the tests write is read
    back **through another request**, so a write that did not land cannot
    pass for one that did.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    built = build_chain(store, workspace_root, comments=(a_comment("201"),))
    from labcairn.db.models import EditActionRow, ResponseLinkRow
    from labcairn.papers.feedback import record_feedback, set_issue_key

    events = record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    session = built.context.store.session
    for event, key in zip(events, (KEY_ONE,), strict=True):
        edit_action_id = f"edit-{event.feedback_id[-6:]}"
        session.add(
            EditActionRow(
                edit_action_id=edit_action_id,
                feedback_id=event.feedback_id,
                version_edge_id=built.edge_id,
                actor_kind="student",
                grade="observed",
                created_at=MOMENT,
            )
        )
        session.add(
            ResponseLinkRow(
                response_link_id=f"resp-{key[-2:]}",
                feedback_id=event.feedback_id,
                edit_action_id=edit_action_id,
                state="addressed",
                grade="human_verified",
                decided_by="user",
                decided_at=LATER,
                evidence_refs=[f"check:{key}"],
                created_at=LATER,
            )
        )
        set_issue_key(built.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
    session.flush()
    app = create_app(built.context)
    with TestClient(app) as wired:
        token = str(wired.get("/session").json()["token"])
        headers = {"Authorization": f"Bearer {token}"}
        yield wired, headers, built.context, built.project_id


def _propose_over_api(context: ApplicationContext, *, proposed_by: str = PROPOSER) -> str:
    """A confirmed rule written through the layer, and its id.

    **The write is committed here**, so the request that follows reads a
    row the store holds rather than a row the test's own session is
    holding — and so the session's transaction is closed before the
    service asks for the write lock. The reason is
    ``tests/test_api.py``'s ``candidate_rule`` fixture's, word for word:
    the service's unit of work and the test's session are two
    transactions on one database.
    """
    rule = _propose(context, proposed_by=proposed_by)
    confirm_rule(context, rule_id=rule.rule_id, confirmed_by=MENTOR, now=LATER)
    context.store.session.commit()
    return str(rule.rule_id)


def test_the_api_publishes_and_retracts_a_rule(
    api: tuple[TestClient, dict[str, str], ApplicationContext, str],
) -> None:
    """The doors do what the layer's operations do, and the record says so.

    **The route asks the layer, and the layer asks its own questions.** A
    publication lands, the rule is served to a project that is not its
    own, a retraction closes the door again — and every read goes back
    through the service, so the answer is what a client would see.
    """
    client, headers, context, _ = api
    rule_id = _propose_over_api(context)
    _second_project(context, "proj-2")

    published = client.post(
        f"/guidance/rules/{rule_id}/publish",
        json={"user_id": MENTOR},
        headers=headers,
    )
    assert published.status_code == 200, published.text
    body: dict[str, Any] = published.json()
    assert body["shared_scope"] == "group"
    assert body["published_by"] == MENTOR
    assert body["state"] == "confirmed"

    served = client.get("/guidance/usable", params={"project_id": "proj-2"}, headers=headers)
    assert served.status_code == 200, served.text
    assert [item["rule_id"] for item in served.json()] == [rule_id]

    retracted = client.post(f"/guidance/rules/{rule_id}/retract", headers=headers)
    assert retracted.status_code == 200, retracted.text
    assert retracted.json()["shared_scope"] == "private"

    served_after = client.get("/guidance/usable", params={"project_id": "proj-2"}, headers=headers)
    assert served_after.status_code == 200
    assert served_after.json() == []


def test_the_api_refuses_a_publication_by_the_proposer(
    api: tuple[TestClient, dict[str, str], ApplicationContext, str],
) -> None:
    """The door renders the second-reader refusal the service renders every refusal.

    **A refusal is an answer, not a crash.** The proposer's publication is
    refused with the memory's own reason, and the rule keeps the scope it
    had — a door that says no writes nothing.
    """
    client, headers, context, _ = api
    rule_id = _propose_over_api(context, proposed_by=PROPOSER)

    refused = client.post(
        f"/guidance/rules/{rule_id}/publish",
        json={"user_id": PROPOSER},
        headers=headers,
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["reason"] == ApplicationRefusal.GUIDANCE_PUBLISHER_IS_PROPOSER.value

    read_back = client.get(f"/guidance/rules/{rule_id}", headers=headers)
    assert read_back.status_code == 200
    assert read_back.json()["shared_scope"] == "private"


def test_the_api_refuses_to_publish_a_candidate(
    api: tuple[TestClient, dict[str, str], ApplicationContext, str],
) -> None:
    """A candidate reaches no group through the door either.

    **§8.5's line, at the wire.** The service refuses a candidate's
    publication with the layer's own reason — a client that asks the door
    to share unreviewed experience learns that, by name.
    """
    client, headers, context, _ = api
    rule = _propose(context)
    context.store.session.commit()

    refused = client.post(
        f"/guidance/rules/{rule.rule_id}/publish",
        json={"user_id": MENTOR},
        headers=headers,
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["reason"] == ApplicationRefusal.GUIDANCE_PUBLISH_NOT_CONFIRMED.value


def test_the_usable_listing_without_a_project_serves_everything(
    api: tuple[TestClient, dict[str, str], ApplicationContext, str],
) -> None:
    """The listing keeps its own shape when no project is named.

    **The parameter is optional, and omitting it is the workbench's view**:
    every standing confirmed rule, whatever project it was learned in and
    whether or not it was published. A caller that does not ask about
    projects is not answered about them.
    """
    client, headers, context, _ = api
    rule_id = _propose_over_api(context)

    served = client.get("/guidance/usable", headers=headers)
    assert served.status_code == 200, served.text
    assert [item["rule_id"] for item in served.json()] == [rule_id]


def test_the_api_refuses_an_unsigned_publication(
    api: tuple[TestClient, dict[str, str], ApplicationContext, str],
) -> None:
    """A publication nobody signs is not a publication.

    **The door asks the same question the confirmation's door asks**: name
    the person whose word it is. A body that names nobody is refused
    before the layer is reached — a signature is the record's fact, not a
    field the layer may guess.
    """
    client, headers, context, _ = api
    rule_id = _propose_over_api(context)

    for user_id in ("", "   "):
        refused = client.post(
            f"/guidance/rules/{rule_id}/publish",
            json={"user_id": user_id},
            headers=headers,
        )
        # The contract's ``min_length`` refuses the empty name at the wire
        # (422); the whitespace name passes the contract and is refused by
        # the door's own check (403). **Both are the refusal that says:
        # name the person whose word it is.**
        assert refused.status_code in (403, 422), refused.text


# -- the migration builds and unbuilds the sharing ----------------------------- #


def test_the_migration_builds_the_sharing_and_unbuilds_it(tmp_path: Path) -> None:
    """``upgrade head`` builds the sharing, and the way back unbuilds it.

    **A migration is a door that swings both ways.** The upgrade adds the
    scope, the publisher and the moment — and every row that predates the
    revision is ``private``, which is the fact. The downgrade removes all
    three and the two checks, and upgrading again rebuilds them.
    """
    from labcairn.db.migrations import (
        current_revision,
        downgrade_to_base,
        head_revision,
        upgrade_to_head,
    )

    target = tmp_path / "sharing.db"
    upgrade_to_head(target)
    assert current_revision(target) == head_revision()

    import sqlite3

    with sqlite3.connect(str(target)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(guidance_rules)")}
        assert {"shared_scope", "published_by", "published_at"} <= columns, (
            "the upgrade adds the sharing's three columns"
        )
        defaults = {
            row[1]: row[4] for row in connection.execute("PRAGMA table_info(guidance_rules)")
        }
        assert defaults["shared_scope"] == "'private'", (
            "every row that predates the revision is private — the default is the fact"
        )
        check_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='guidance_rules'"
        ).fetchone()[0]
        assert "shared_scope IN ('private', 'group')" in check_sql
        assert "a_publication_carries_its_publisher_and_moment" in check_sql

    downgrade_to_base(target)
    assert current_revision(target) is None
    upgrade_to_head(target)
    assert current_revision(target) == head_revision()

    with sqlite3.connect(str(target)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(guidance_rules)")}
        assert {"shared_scope", "published_by", "published_at"} <= columns, (
            "the re-upgrade rebuilds the sharing"
        )
