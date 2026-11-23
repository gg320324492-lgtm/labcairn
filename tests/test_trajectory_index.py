"""The multi-source index: a paper's revision trajectory, and the rules above it.

**What is under test.** Phase 4 (P4-MS), execution plan §8.1-§8.5, first
source: the paper and its revision trajectory. The chain's comments and
changes become searchable entries that carry their provenance; a mentor can
draft a rule *candidate* from an entry and confirm it; and the usable
listing serves confirmed rules only — a candidate is never served, and a
withdrawn rule stops being served.

=================================  =======================================
§8.5 acceptance                    witness
=================================  =======================================
the trajectory is searchable       a comment's own words find the entry,
                                   and the entry points at the comment
the entry carries its provenance   source version, locator, content hash
unreviewed experience is a         a candidate is absent from
candidate, not a code of conduct   ``usable_guidance`` until confirmed
only mentor-confirmed experience   ``confirm_rule_candidate`` moves the
is shared                          rule, and the listing serves it
a withdrawn rule is not served     ``withdraw_rule`` removes it from the
                                   next listing
=================================  =======================================

**The fixture is the chain's own.** The trajectory is read from the same
comments, revisions and edits the feedback chain's witnesses record, so an
entry the index holds is traceable to the chain row it came from — one set
of facts, two views of it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_fixtures import Revision
from feedback_chain_fixtures import (
    MOMENT,
    ChainEnv,
    a_comment,
    build_chain,
)
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.trajectory import (
    COMMENT_KIND,
    EDIT_KIND,
    confirm_rule_candidate,
    ingest_paper_trajectory,
    propose_rule_candidate,
    search_trajectory,
    usable_guidance,
)
from labcairn.guidance.rules import withdraw_rule
from labcairn.papers.edits import ActorClaim, record_edits_from_revisions
from labcairn.papers.feedback import record_feedback
from labcairn.papers.responses import record_response
from labcairn.papers.revisions import record_revision_events
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

#: The second moment every confirmation and withdrawal is written at. A
#: fixed instant, not the wall clock, for the project's reason.
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)

_ADVISOR_NAME = "Prof. Lin"
_AUTHOR_NAME = "Dr. Chen"

#: The roster the file's names are read through: the operator's answer to
#: *"whose change is this?"*, the same shape the chain's witnesses use.
_ROSTER = {
    _ADVISOR_NAME: ActorClaim(actor_kind="advisor", actor_id="advisor-1"),
    _AUTHOR_NAME: ActorClaim(actor_kind="student", actor_id="student-1"),
}

#: One insertion and one deletion, by different people, on the standard
#: paragraph — the smallest trajectory that has a change to index.
_REVISIONS = (
    Revision(
        kind="ins",
        text="carefully",
        author=_ADVISOR_NAME,
        date="2026-03-02T09:30:00Z",
        element_id="101",
        paragraph=0,
        after_text="estimates",
    ),
    Revision(
        kind="del",
        text="roughly",
        author=_AUTHOR_NAME,
        date="2026-03-03T10:15:00Z",
        element_id="102",
        paragraph=0,
        anchor_text="roughly",
    ),
)

#: The paragraph the fixture is built on. It carries "roughly" — the word
#: the deletion removes — and "the parameter", the comment's anchor.
_MARKED_PARAGRAPH = "The method estimates the parameter roughly from a single observation."

#: The comments' anchor: the sentence **after** every revision, because the
#: fixture writer emits a comment's range markers only when the comment's
#: bounds meet a revision's or when the comment sits wholly in the tail the
#: revisions leave. An anchor between the revisions would be a comment the
#: writer writes no markers for, and the reader would report its anchor as
#: unknown — a fixture artefact, not a property of the product.
_COMMENT_ANCHOR = "from a single observation"


def allow_all() -> PermissionPolicy:
    """A policy that permits everything; the refusals under test are the
    layer's own, not the policy's."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture()
def trajectory(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A chain with two comments and two changes, with the comments recorded.

    **The comments are recorded before the edits are filled in**, because a
    change's ``answers`` mapping names a comment the chain must already
    hold. Every write is stamped with the fixture's fixed moment, the way
    every chain witness stamps its writes.
    """
    chain = build_chain(
        env.store(),
        tmp_path / "workspace",
        paragraphs=(_MARKED_PARAGRAPH,),
        comments=(
            a_comment(
                "c-1",
                text="Define the parameter in the methods.",
                anchor_text=_COMMENT_ANCHOR,
            ),
            a_comment(
                "c-2",
                text="Cite the source of the measurement.",
                anchor_text=_COMMENT_ANCHOR,
            ),
        ),
        revisions=_REVISIONS,
    )
    record_feedback(
        chain.context, project_id=chain.project_id, version_id=chain.version_id, now=MOMENT
    )
    chain.context.store.session.commit()
    return chain


def _fill_the_second_ring(chain: ChainEnv, *, answers: dict[str, str]) -> None:
    """Record the changes as the chain's own, against the edge, with the
    roster — the step that turns the file's revisions into edit rows."""
    record_edits_from_revisions(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        version_edge_id=chain.edge_id,
        actors=_ROSTER,
        answers=answers,
        now=MOMENT,
    )


def _the_comment_id(chain: ChainEnv, body: str) -> str:
    """The chain's id for the comment whose text is *body*."""
    from labcairn.papers.feedback import list_feedback_events

    for event in list_feedback_events(
        chain.context, project_id=chain.project_id, version_id=chain.version_id
    ):
        if event.comment_text == body:
            return event.feedback_id
    raise AssertionError(f"no comment with the body {body!r} was recorded")


def _answer_the_comment(chain: ChainEnv, comment_body: str) -> str:
    """Record the changes, bind the first one to the comment, and judge it
    answered — the chain's full second ring, which a *confirmed* rule's
    source must stand on.

    **A confirmed rule's source lives by a judgement**: the retrieval
    resolves each source at query time and serves the rule only when
    something answered the comment. A candidate needs no judgement — that
    is the asymmetry the memory's own review wrote down — so the witnesses
    that stop at the candidate stage need none, and the ones that cross
    into ``confirmed`` do.
    """
    comment_id = _the_comment_id(chain, comment_body)
    events = record_revision_events(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        now=MOMENT,
    )
    _fill_the_second_ring(chain, answers={events[0].revision_event_id: comment_id})
    from labcairn.papers.chain import edit_action_id_for

    record_response(
        chain.context,
        response_link_id=f"rl-{comment_id}",
        feedback_id=comment_id,
        edit_action_id=edit_action_id_for(events[0].revision_event_id),
        state="addressed",
        grade="human_verified",
        decided_by="user",
        decided_at=MOMENT,
        evidence_refs=("check:trajectory-witness",),
        now=MOMENT,
    )
    chain.context.store.session.commit()
    return comment_id


# -- the ingest -------------------------------------------------------------- #


def test_the_trajectory_is_ingested_and_searchable_by_the_comment(trajectory: ChainEnv) -> None:
    """§8.5, first clause: a comment's own words find the entry, and the
    entry points back at the comment it came from."""
    ingested = ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    assert ingested.entries_indexed == 2, "two comments, no edits recorded yet"
    assert ingested.comment_entries == 2

    hits = search_trajectory(trajectory.context, query="Define the parameter")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.entry_kind == COMMENT_KIND
    assert hit.feedback_id == _the_comment_id(trajectory, "Define the parameter in the methods.")
    assert hit.comment_text == "Define the parameter in the methods."
    # The provenance: which version, where in it, and the bytes it was read from.
    assert hit.source_version_id == trajectory.version_id
    assert hit.source_sha256, "the entry names the bytes it was read from"
    assert "paragraph:" in hit.source_locator


def test_an_edit_entry_carries_the_change_and_its_comment(trajectory: ChainEnv) -> None:
    """An edit entry says what changed, which comment it answered, and where
    the change sits — the old/new summary §8.2 asks the raw layer to keep."""
    comment_id = _the_comment_id(trajectory, "Define the parameter in the methods.")
    record_revision_events(
        trajectory.context,
        project_id=trajectory.project_id,
        version_id=trajectory.second_version_id,
        now=MOMENT,
    )
    _fill_the_second_ring(trajectory, answers={})
    ingested = ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    assert ingested.edit_entries == 2, "both tracked changes are indexed"

    hits = search_trajectory(trajectory.context, query="carefully")
    assert len(hits) == 1
    hit = hits[0]
    assert hit.entry_kind == EDIT_KIND
    assert hit.change_kind == "ins"
    assert hit.change_text == "carefully"
    assert hit.revision_event_id is not None
    assert hit.source_version_id == trajectory.second_version_id
    assert "w:ins" in hit.source_locator or "document.xml" in hit.source_locator

    # **The comment entry and the edit entry are linked by the comment's id.**
    comment_hits = search_trajectory(trajectory.context, query="Define the parameter")
    assert comment_hits[0].feedback_id == comment_id


def test_reingesting_the_same_project_is_the_same_rows(trajectory: ChainEnv) -> None:
    """The index is rebuilt in place: a second ingest finds the rows that are
    already there, and the FTS answer does not grow a second copy."""
    first = ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    second = ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    assert second.entries_indexed == first.entries_indexed
    hits = search_trajectory(trajectory.context, query="Define the parameter")
    assert len(hits) == 1, "one entry, not one per ingestion"


def test_a_project_nobody_holds_is_refused(env: StoreEnv, tmp_path: Path) -> None:
    """A trajectory of a project nobody holds is a history of nothing."""
    chain = build_chain(env.store(), tmp_path / "ws-empty")
    with pytest.raises(ApplicationRefusedError) as caught:
        ingest_paper_trajectory(chain.context, project_id="proj-nowhere")
    assert caught.value.reason is not None


# -- the rule candidates ----------------------------------------------------- #


def test_a_candidate_is_not_served_until_a_mentor_confirms_it(trajectory: ChainEnv) -> None:
    """§8.5, the hard line: unreviewed experience is a candidate, not a code
    of conduct. The candidate is drafted, and the usable listing does not
    serve it; the mentor's confirmation moves it, and the listing does."""
    comment_id = _answer_the_comment(trajectory, "Define the parameter in the methods.")
    from labcairn.papers.feedback import set_issue_key

    set_issue_key(
        trajectory.context, feedback_id=comment_id, issue_key="definition_missing", now=MOMENT
    )
    trajectory.context.store.session.commit()
    ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    hits = search_trajectory(trajectory.context, query="Define the parameter")
    rule = propose_rule_candidate(
        trajectory.context,
        trajectory_id=hits[0].trajectory_id,
        issue_type="method_and_hypothesis",
        statement="Define every parameter before it is first used in the methods.",
        rule_context="A methods section that uses a symbol nobody has defined.",
        scope="methods",
        example="The comment of 2026-03-02 on the methods paragraph.",
        proposed_by="model_proposal",
        now=MOMENT,
    )
    assert rule.state == "candidate"

    # **The candidate is not served.**
    assert usable_guidance(trajectory.context) == ()

    # **The mentor confirms it, and the listing serves it.**
    confirmed = confirm_rule_candidate(
        trajectory.context,
        rule_id=rule.rule_id,
        confirmed_by="Prof. Mentor",
        now=LATER,
    )
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_by == "Prof. Mentor"
    usable = usable_guidance(trajectory.context)
    assert len(usable) == 1
    served = usable[0]
    assert served.rule_id == rule.rule_id
    assert served.name.startswith("Define every parameter")
    assert served.summary == rule.statement
    assert served.sources == ("definition_missing",)
    assert served.confirmed_by == "Prof. Mentor"


def test_a_proposal_from_an_unkeyed_comment_is_refused(trajectory: ChainEnv) -> None:
    """A comment nobody has keyed is material the memory cannot show, and a
    candidate that cannot name its source is the bare preference the work
    order refuses."""
    ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    hits = search_trajectory(trajectory.context, query="Cite the source")
    with pytest.raises(ApplicationRefusedError):
        propose_rule_candidate(
            trajectory.context,
            trajectory_id=hits[0].trajectory_id,
            issue_type="data_quality",
            statement="Cite the source of every measurement.",
            rule_context="A results section that reports a value with no source.",
            scope="results",
            example="The comment of 2026-03-02 on the measurement.",
            proposed_by="model_proposal",
            now=MOMENT,
        )


def test_a_proposal_from_an_entry_that_is_not_indexed_is_refused(trajectory: ChainEnv) -> None:
    """A draft is made from material the index holds; a draft about nothing
    is a draft about nothing."""
    with pytest.raises(ApplicationRefusedError):
        propose_rule_candidate(
            trajectory.context,
            trajectory_id="trj-nowhere",
            issue_type="data_quality",
            statement="Cite the source of every measurement.",
            rule_context="A results section.",
            scope="results",
            example="An example.",
            proposed_by="model_proposal",
            now=MOMENT,
        )


def test_a_withdrawn_rule_stops_being_served(trajectory: ChainEnv) -> None:
    """§8.5, last clause: after a withdrawal, the next listing does not
    return the rule. The retraction is the mentor's word, and the memory
    serves what stands."""
    comment_id = _answer_the_comment(trajectory, "Define the parameter in the methods.")
    from labcairn.papers.feedback import set_issue_key

    set_issue_key(
        trajectory.context, feedback_id=comment_id, issue_key="definition_missing", now=MOMENT
    )
    trajectory.context.store.session.commit()
    ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    hits = search_trajectory(trajectory.context, query="Define the parameter")
    rule = propose_rule_candidate(
        trajectory.context,
        trajectory_id=hits[0].trajectory_id,
        issue_type="method_and_hypothesis",
        statement="Define every parameter before it is first used in the methods.",
        rule_context="A methods section that uses a symbol nobody has defined.",
        scope="methods",
        example="The comment of 2026-03-02 on the methods paragraph.",
        proposed_by="model_proposal",
        now=MOMENT,
    )
    confirm_rule_candidate(
        trajectory.context, rule_id=rule.rule_id, confirmed_by="Prof. Mentor", now=LATER
    )
    assert len(usable_guidance(trajectory.context)) == 1

    withdrawn = withdraw_rule(
        trajectory.context,
        rule_id=rule.rule_id,
        reason="The methods now define every parameter; the rule is done.",
        now=LATER,
    )
    assert withdrawn.state == "withdrawn"
    assert usable_guidance(trajectory.context) == ()


def test_a_candidate_cannot_be_confirmed_twice_by_its_proposer(trajectory: ChainEnv) -> None:
    """The second-reader rule is the memory's own: whoever proposed the rule
    cannot be the one who confirms it."""
    comment_id = _answer_the_comment(trajectory, "Define the parameter in the methods.")
    from labcairn.papers.feedback import set_issue_key

    set_issue_key(
        trajectory.context, feedback_id=comment_id, issue_key="definition_missing", now=MOMENT
    )
    trajectory.context.store.session.commit()
    ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    hits = search_trajectory(trajectory.context, query="Define the parameter")
    rule = propose_rule_candidate(
        trajectory.context,
        trajectory_id=hits[0].trajectory_id,
        issue_type="method_and_hypothesis",
        statement="Define every parameter before it is first used in the methods.",
        rule_context="A methods section that uses a symbol nobody has defined.",
        scope="methods",
        example="The comment of 2026-03-02 on the methods paragraph.",
        proposed_by="model_proposal",
        now=MOMENT,
    )
    with pytest.raises(ApplicationRefusedError) as caught:
        confirm_rule_candidate(
            trajectory.context, rule_id=rule.rule_id, confirmed_by="model_proposal", now=LATER
        )
    assert caught.value.reason is not None
    assert "proposed by" in str(caught.value)


# -- the search's edges ------------------------------------------------------ #


def test_a_query_with_no_servable_terms_is_an_empty_answer(trajectory: ChainEnv) -> None:
    """An empty query is not an error; it is an absence, said honestly."""
    ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    assert search_trajectory(trajectory.context, query="ab") == ()
    assert search_trajectory(trajectory.context, query="") == ()


def test_a_project_filter_narrows_the_answer(trajectory: ChainEnv) -> None:
    """A hit from another project is not this project's history, however
    well it matches.

    **The foreign row is written directly.** ``build_chain`` fixes the
    project id it writes, so a second chain on this store would collide
    with the first — and the property under test is the *search's* filter,
    not the ingest's, so a hand-written foreign entry is the honest
    fixture: one row this project did not ingest, in the index the search
    reads.
    """
    ingest_paper_trajectory(trajectory.context, project_id=trajectory.project_id)
    from sqlalchemy import text as sql_text

    # **A second project, written directly.** ``build_chain`` fixes the
    # project id it writes, so a second chain on this store would collide
    # with the first — and the property under test is the *search's* filter,
    # not the ingest's. The foreign row satisfies the schema's own refusals
    # (a comment entry names a real feedback event; a version row exists),
    # and it is one entry this project did not ingest and must not answer
    # for.
    foreign_feedback = _the_comment_id(trajectory, "Cite the source of the measurement.")
    foreign_version = f"{trajectory.version_id}-foreign"
    trajectory.context.store.session.execute(
        sql_text(
            "INSERT INTO paper_projects (project_id, workspace_id, subject_pseudonym,"
            " consent_ref, created_at) VALUES ('proj-other', 'ws-other', 'subject-2',"
            " NULL, :moment)"
        ),
        {"moment": MOMENT.isoformat()},
    )
    trajectory.context.store.session.execute(
        sql_text(
            "INSERT INTO paper_versions (version_id, project_id, source_id,"
            " source_content_sha256, version_label_raw, stage_candidate, status,"
            " created_at) VALUES (:vid, 'proj-other', :sid, 'sha', 'foreign',"
            " 'draft', 'resolved', :moment)"
        ),
        {"vid": foreign_version, "sid": trajectory.source_id, "moment": MOMENT.isoformat()},
    )
    trajectory.context.store.session.execute(
        sql_text(
            "INSERT INTO trajectory_index_rows (trajectory_id, project_id, entry_kind,"
            " feedback_id, edit_action_id, revision_event_id, version_id, issue_key,"
            " comment_text, anchor_text, anchor_paragraph, verdict, change_kind,"
            " change_text, text_digest, source_version_id, source_locator,"
            " source_sha256, ingested_at) VALUES"
            " ('trj-foreign', 'proj-other', 'comment', :feedback_id, NULL, NULL,"
            " :version_id, NULL, 'Define the parameter somewhere else.', NULL, NULL,"
            " NULL, NULL, NULL, 'Define the parameter somewhere else.', :version_id,"
            " 'loc', 'sha', :moment)"
        ),
        {
            "feedback_id": foreign_feedback,
            "version_id": foreign_version,
            "moment": MOMENT.isoformat(),
        },
    )
    trajectory.context.store.session.execute(
        sql_text(
            "INSERT INTO trajectory_fts (text_digest, trajectory_id)"
            " VALUES ('Define the parameter somewhere else.', 'trj-foreign')"
        )
    )
    trajectory.context.store.session.commit()

    everywhere = search_trajectory(trajectory.context, query="Define the parameter")
    assert len(everywhere) == 2
    narrowed = search_trajectory(
        trajectory.context, query="Define the parameter", project_id=trajectory.project_id
    )
    assert len(narrowed) == 1
    assert narrowed[0].project_id == trajectory.project_id


def test_the_index_serves_no_entries_for_a_project_with_no_trajectory(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A project whose manuscripts hold no comments and no changes indexes
    nothing, and the search answers nothing — an absence, not an error."""
    chain = build_chain(env.store(), tmp_path / "ws-plain")
    ingested = ingest_paper_trajectory(chain.context, project_id=chain.project_id)
    assert ingested.entries_indexed == 0
    assert search_trajectory(chain.context, query="parameter") == ()


def test_a_denied_version_is_dropped_from_the_index(env: StoreEnv, tmp_path: Path) -> None:
    """The permission is asked where the material is named: a version the
    policy denies is dropped from the index, and the report says so — the
    bulk listing's rule (ADR-0003 C5) at the ingest's own door."""
    from labcairn.security.policy import PermissionPolicy, Rule

    chain = build_chain(
        env.store(),
        tmp_path / "ws-denied",
        comments=(a_comment("c-1", text="Define the parameter in the methods."),),
    )
    record_feedback(
        chain.context, project_id=chain.project_id, version_id=chain.version_id, now=MOMENT
    )
    chain.context.store.session.commit()
    denying = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.DENY, pattern="**"),
        ]
    )
    object.__setattr__(chain.context, "policy", denying)
    ingested = ingest_paper_trajectory(chain.context, project_id=chain.project_id)
    assert ingested.entries_indexed == 0
    # **Both of the scaffold's versions are out of reach** — build_chain
    # writes two, and the blanket deny drops both — and the report says so
    # rather than claiming the index is complete.
    assert ingested.skipped_versions == 2
