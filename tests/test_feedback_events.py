"""The feedback row: a comment found in a manuscript, and its two addresses.

**What is under test.** LC-P2-09 T01: ``feedback_events``, and the
acceptance clauses that carry it — and, at the end of the file, the fifth
table the work order's material held and the chain did not: ``replies``,
the exchange a *reviewer's* objection and *the authors'* answer make.

===========================  ===================================================
A1   both addresses          a comment becomes a row with both of them
A2   the anchored text       the row carries the text, and the offsets and
                             the text agree in the version the row names
A3   unknown metadata        a missing author or date is unknown, never
                             guessed
A4   the version             a row names the version it was written
                             against, and one that names none is refused
A5   an unanchorable comment it is still a comment
A17  a candidate             a model's candidate carries no
                             ``comment_locator``, and a row that claims the
                             advisor's words without having read them is
                             refused
===========================  ===================================================

**Why the schema's refusals are witnessed by writing rows.** The
project's lesson from revision 0007: *"the parity test passed through it,
because the migration and the ORM were mangled identically — a test
comparing two texts cannot catch both being wrong."* So each rule is
witnessed by **writing a row the schema must refuse** and watching the
database refuse it, with a raw ``INSERT`` that bypasses the ORM.

**And the reader's own change is witnessed here too.** The DOCX reader
did not carry a comment's anchored text at all — ``CommentAnchor.text``
was ``""`` on every path — and the chain's first link was empty. The
reader now carries it, and the witness is that the text it carries is
the text at the offsets it reports.

**And the reply's witnesses do not use any material of the owner's.** The
four paragraphs the reply section reads are written here, in this file,
because the repository is public and the paper is not.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_fixtures import Comment, Fixture, Revision, write_fixture
from feedback_chain_fixtures import (
    MOMENT,
    ChainEnv,
    a_comment,
    build_chain,
)
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import chain as chain_layer
from labcairn.application.refusal import (
    CHAIN_REFUSALS,
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refusal_name,
)
from labcairn.application.sources import list_sources
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperProjectRow,
    PaperVersionRow,
    ReplyRow,
    ReplySettlementRow,
    ResponseLinkRow,
    VersionEdgeRow,
)
from labcairn.guidance.retrieval import invalidated_rules, search_rules
from labcairn.guidance.rules import confirm_rule, propose_rule
from labcairn.material.ooxml import (
    CommentAnchor,
    CommentEvent,
    RevisionDocument,
    read_document,
)
from labcairn.papers.chain import ChainRefusal
from labcairn.papers.edits import ActorClaim, EditAction, record_edits_from_revisions
from labcairn.papers.feedback import (
    FeedbackEvent,
    anchor_state,
    list_feedback_events,
    record_feedback,
    set_issue_key,
)
from labcairn.papers.replies import (
    Reply,
    ReplyExchange,
    ReplySettlement,
    list_replies,
    list_reply_settlements,
    list_unsettled_replies,
    record_replies,
    settle_reply,
)
from labcairn.papers.responses import (
    AnswerProposal,
    list_unaddressed,
    propose_responses,
    record_response,
)
from labcairn.papers.revisions import record_revision_events
from labcairn.sources.locators import DocxLocator

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture()
def chain(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A workspace with one manuscript, one comment and one project."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return build_chain(env.store(), workspace, comments=(a_comment("201"),))


def _record(chain: ChainEnv, *, version_id: str | None = None) -> tuple[FeedbackEvent, ...]:
    return record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=version_id or chain.version_id,
        now=MOMENT,
    )


def _raw_insert(session: Session, **overrides: object) -> None:
    """Write a feedback row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "feedback_id": "fb-raw",
        "project_id": "proj-1",
        "version_id": "ver-1",
        "comment_locator": '{"locator_kind": "docx"}',
        "anchor_paragraph": 0,
        "anchor_start": 0,
        "anchor_end": 3,
        "anchor_status": "resolved",
        "anchor_reason": None,
        "anchor_text": "The",
        "anchor_text_sha256": hashlib.sha256(b"The").hexdigest(),
        "comment_text": "Define the parameter.",
        "comment_text_sha256": hashlib.sha256(b"Define the parameter.").hexdigest(),
        "author": "Prof. Lin",
        "author_unknown_reason": None,
        "commented_at": "2026-03-02T09:30:00+00:00",
        "date_unknown_reason": None,
        "grade": "observed",
        "issue_key": None,
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO feedback_events ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


# --------------------------------------------------------------------------- #
# A1 — both addresses
# --------------------------------------------------------------------------- #


def test_a_feedback_row_carries_both_addresses(chain: ChainEnv) -> None:
    """A comment becomes a row with **both** of its addresses.

    **Two addresses because two questions.** ``comment_locator`` names the
    comment element in ``word/comments.xml`` — *what was written* — and the
    anchor names the place in the body — *where it was written about*. A
    row that kept only one would answer only one of them.

    **What breaks it:** a row with no locator (the comment's own address
    dropped) or a row with no anchor (where the comment sits dropped).
    """
    recorded = _record(chain)

    assert len(recorded) == 1, "the one comment in the file became one row"
    event = recorded[0]
    assert event.comment_locator is not None, "the row carries the comment's own address"
    assert event.comment_locator.part == "word/comments.xml", (
        "the comment's own address is into the comments part, not the body"
    )
    assert event.comment_locator.view == "accepted"
    assert event.anchor_paragraph == 0, "the body-side anchor names the paragraph"
    assert event.anchor_start is not None and event.anchor_end is not None, (
        "the body-side anchor names the range it covers"
    )
    assert event.anchor_status == "resolved"


# --------------------------------------------------------------------------- #
# A2 — the anchored text
# --------------------------------------------------------------------------- #


def test_the_anchored_text_agrees_with_the_offsets_in_the_version_named(
    chain: ChainEnv,
) -> None:
    """The row carries the text its anchor names, and the two agree.

    **The text is the baseline's text, at the offsets the row names.** The
    reader's offsets are into the paragraph's *rejected* text — the
    manuscript as it read before the revisions — and the row's text is cut
    from that same text, so the offset and the text agree by construction
    and a reader can check that they do.

    **And the hash is of that text**, which is what makes a drifted anchor
    detectable rather than merely different.
    """
    recorded = _record(chain)
    event = recorded[0]

    document = read_document(chain.manuscript.read_bytes())
    baseline = document.baseline_paragraphs[event.anchor_paragraph or 0]
    assert event.anchor_text == baseline[event.anchor_start or 0 : event.anchor_end or 0], (
        "the anchored text is not the text the offsets name"
    )
    assert event.anchor_text_sha256 == hashlib.sha256(event.anchor_text.encode()).hexdigest()

    # And the anchor is fresh: the manuscript's bytes have not changed
    # under it.
    assert anchor_state(chain.context, feedback_id=event.feedback_id, now=MOMENT) == "fresh"


def test_the_reader_carries_the_text_a_comments_anchor_covers(chain: ChainEnv) -> None:
    """The reader itself now carries the anchored text.

    **It did not before.** ``CommentAnchor.text`` was ``""`` on every
    return path, so the chain's first link was empty and the row had
    nothing to carry. The reader's own witness is that the text it
    reports is the text at the offsets it reports.

    **What breaks it:** a reader that reports an empty anchor text again,
    or one that reports text that is not at the offsets.
    """
    document = read_document(chain.manuscript.read_bytes())

    assert document.comments, "the manuscript holds a comment"
    for comment in document.comments:
        anchor = comment.anchor
        if anchor.status != "resolved":
            continue
        baseline = document.baseline_paragraphs[anchor.paragraph or 0]
        assert anchor.text == baseline[anchor.start or 0 : anchor.end or 0], (
            f"comment {comment.comment_id}: the anchored text is not the text the offsets name"
        )


# --------------------------------------------------------------------------- #
# A3 — unknown metadata
# --------------------------------------------------------------------------- #


def test_a_missing_author_or_date_is_unknown_and_never_guessed(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A comment with no author has an unknown author, and never a guess.

    **Unknown is ``None`` plus a named reason** — not an empty string, and
    not the file's mtime. The reader already refuses to guess, and the row
    inherits that refusal rather than re-deciding it.

    **The file is edited to have no author attribute at all**, because an
    *empty* author is a different case: the corpus says so, and a comment
    signed by nobody is not the same as a comment whose signature is
    missing.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("301"),),
        bare_comment_ids=("301",),
    )

    recorded = _record(chain)
    assert len(recorded) == 1
    event = recorded[0]

    assert event.author is None, "a missing author is unknown, not a guess"
    assert event.author_unknown_reason, "the unknown names why it is unknown"
    assert event.commented_at is None, "a missing date is unknown, not a guess"
    assert event.date_unknown_reason, "the unknown names why it is unknown"

    # And nothing was filled in from the file's own metadata.
    row = env.store().session.get(FeedbackEventRow, event.feedback_id)
    assert row is not None
    assert row.author is None
    assert row.commented_at is None


# --------------------------------------------------------------------------- #
# A4 — the version
# --------------------------------------------------------------------------- #


def test_a_feedback_row_names_its_version_and_one_that_names_none_is_refused(
    chain: ChainEnv,
) -> None:
    """A feedback row names the version it was written against.

    **And a row that names none is refused** — by the schema's NOT NULL and
    by the schema's foreign key. A comment that names no manuscript state
    cannot be said to have been answered by any change, because there is
    no "before" to have been answered *against*.

    **What breaks it:** a nullable ``version_id``, or a foreign key that
    does not fire.
    """
    recorded = _record(chain)
    assert recorded[0].version_id == chain.version_id, "the row names its version"

    session = chain.context.store.session
    with pytest.raises(IntegrityError):
        _raw_insert(session, feedback_id="fb-no-version", version_id=None)
    session.rollback()

    with pytest.raises(IntegrityError):
        _raw_insert(session, feedback_id="fb-no-such-version", version_id="ver-nope")
    session.rollback()


def test_a_feedback_row_for_a_version_that_is_not_there_is_refused(chain: ChainEnv) -> None:
    """The operation refuses a version the store does not hold.

    **A refusal, not an empty result.** Recording a comment against a
    version nobody holds would write a row that names nothing.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        _record(chain, version_id="ver-nope")

    assert caught.value.reason is ApplicationRefusal.CHAIN_VERSION_NOT_FOUND


# --------------------------------------------------------------------------- #
# A5 — an unanchorable comment
# --------------------------------------------------------------------------- #


def test_an_unanchorable_comment_is_still_a_comment(env: StoreEnv, tmp_path: Path) -> None:
    """A comment the reader could not place is still a comment.

    **It is written with its body, its author and the reason its anchor
    is unknown** — because a comment the reader could not place is a
    comment a person still wrote, and dropping it would make the chain's
    silence indistinguishable from its having nothing to say.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("401", anchor="none"),),
    )

    recorded = _record(chain)

    assert len(recorded) == 1, "the unanchorable comment is still a comment"
    event = recorded[0]
    assert event.comment_text == "Define the parameter.", "its body is recorded"
    assert event.author == "Prof. Lin", "its author is recorded"
    assert event.anchor_status == "unknown"
    assert event.anchor_reason, "the reason the anchor is unknown is named"
    assert event.anchor_start is None and event.anchor_end is None


# --------------------------------------------------------------------------- #
# A17 — a candidate is not a comment
# --------------------------------------------------------------------------- #


def test_a_candidate_does_not_claim_the_advisors_words(chain: ChainEnv) -> None:
    """A model's candidate carries no locator, and a row that claims the
    advisor's words without having read them is refused.

    **The mechanism is structural, not a promise.** The row that holds a
    locator is the row the reader wrote: a row nobody read is ``inferred``,
    and the schema refuses an inferred row that carries a locator — and
    refuses an observed row that carries none. A model's candidate is a
    *response link* at grade ``inferred``, and the response table has **no
    ``comment_locator`` column at all**, so there is nowhere for it to put
    the advisor's words.

    **What breaks it:** a constraint that lets an inferred row carry a
    locator, or a response table that grows a column for the comment's
    text.
    """
    session = chain.context.store.session

    # An inferred row that carries the locator it did not read.
    with pytest.raises(IntegrityError):
        _raw_insert(session, feedback_id="fb-inferred", grade="inferred")
    session.rollback()

    # An observed row that carries no locator at all.
    with pytest.raises(IntegrityError):
        _raw_insert(session, feedback_id="fb-unread", comment_locator=None)
    session.rollback()

    # An inferred row that quotes the advisor anyway.
    with pytest.raises(IntegrityError):
        _raw_insert(
            session,
            feedback_id="fb-inferred-words",
            grade="inferred",
            comment_locator=None,
        )
    session.rollback()

    # And the response table has nowhere to put the advisor's words.
    columns = {
        column["name"] for column in inspect(session.get_bind()).get_columns("response_links")
    }
    assert "comment_locator" not in columns, (
        "the response table must hold no comment locator: a model's candidate points "
        "at a comment, it does not restate the comment"
    )
    assert "comment_text" not in columns, (
        "the response table must hold no copy of the advisor's words"
    )


# --------------------------------------------------------------------------- #
# the refusal vocabulary
# --------------------------------------------------------------------------- #


def test_every_chain_refusal_has_a_layer_name() -> None:
    """The chain's vocabulary and the layer's are closed, **both ways**.

    **The second direction is the one that catches drift.** A member
    added to the layer's vocabulary with no reason mapping to it is a name
    no refusal can ever carry — and it is exactly the shape the intake's
    missing ``NO_GRANT`` had taken.
    """
    unmapped = {reason for reason in ChainRefusal if reason not in CHAIN_REFUSALS}
    assert not unmapped, (
        f"the feedback chain can refuse with {unmapped}, which the layer cannot name"
    )
    assert len(CHAIN_REFUSALS) == len(set(ChainRefusal))
    invented = {
        layer_reason
        for layer_reason in CHAIN_REFUSALS.values()
        if layer_reason not in set(ApplicationRefusal)
    }
    assert not invented, f"the mapping names reasons the layer does not have: {invented}"

    named = {reason for reason in ApplicationRefusal if reason.name.startswith("CHAIN_")}
    assert named == set(CHAIN_REFUSALS.values()), (
        "the layer's chain names and the reasons that reach them differ: "
        f"{sorted(reason.value for reason in named ^ set(CHAIN_REFUSALS.values()))}"
    )

    for reason, name in CHAIN_REFUSALS.items():
        assert name.value == f"chain_{reason.value}", (
            f"{reason} is named {name.value!r} by the layer"
        )
        assert chain_refusal_name(reason) is name


# --------------------------------------------------------------------------- #
# the issue key
# --------------------------------------------------------------------------- #


def test_a_comment_with_no_key_is_uncategorised(chain: ChainEnv) -> None:
    """A comment nobody keyed is uncategorised, not keyed by similarity.

    **The same wording is not the same issue**, and the same issue is not
    the same wording. So the operation never derives a key from the text:
    a key is a person's judgement, and until somebody makes it the
    comment is uncategorised.

    **The named clause for this lives in the assessment's file**, beside
    the recurrence it is about.
    """
    recorded = _record(chain)

    assert recorded[0].issue_key is None, (
        "a comment nobody keyed is uncategorised, not keyed by similarity"
    )


def test_a_key_is_given_and_a_key_already_given_is_not_replaced(chain: ChainEnv) -> None:
    """A key is a person's judgement, and it is given rather than derived.

    **And a key already given is not replaced silently.** A change of
    judgement is a correction, and the project's rule is that a
    correction produces a new record rather than an overwrite.
    """
    recorded = _record(chain)
    feedback_id = recorded[0].feedback_id

    keyed = set_issue_key(
        chain.context, feedback_id=feedback_id, issue_key="parameter-definition", now=MOMENT
    )
    assert keyed.issue_key == "parameter-definition"

    with pytest.raises(ApplicationRefusedError) as caught:
        set_issue_key(
            chain.context, feedback_id=feedback_id, issue_key="something-else", now=MOMENT
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_ISSUE_KEY_MAY_NOT_BE_INFERRED

    with pytest.raises(ApplicationRefusedError) as caught:
        set_issue_key(chain.context, feedback_id=feedback_id, issue_key="   ", now=MOMENT)
    assert caught.value.reason is ApplicationRefusal.CHAIN_ISSUE_KEY_MAY_NOT_BE_INFERRED


def test_the_listing_holds_the_comments_the_chain_found(chain: ChainEnv) -> None:
    """The listing is the chain's own answer to "what did they write?".

    **And it is filtered by the policy rather than refused**, ADR-0003 C5's
    rule for a bulk listing.
    """
    recorded = _record(chain)

    listed = list_feedback_events(chain.context, project_id=chain.project_id)

    assert len(listed) == 1
    assert listed[0].feedback_id == recorded[0].feedback_id


# --------------------------------------------------------------------------- #
# the layer's own issue-key listing
# --------------------------------------------------------------------------- #


def _a_chain_with_comments(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A chain with three comments in the first round and one in the second.

    **Three and one, so that the versions can be told apart.** A listing
    that narrows to the versions named is a different answer from one that
    does not, and a test that has only one version cannot tell them apart.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return build_chain(
        env.store(),
        workspace,
        comments=(
            a_comment("201", text="Define the parameter."),
            a_comment("202", text="Name the core."),
            a_comment("203", text="Give the units."),
        ),
        second_comments=(a_comment("204", text="Report the depth."),),
    )


def _the_comments(chain: ChainEnv, version_id: str) -> dict[str, str]:
    """The comments of one version, by their words, with their ids.

    **Read out of the manuscript by the reader**, so the rows are rows the
    product wrote — and keyed afterwards, because a key is given rather
    than derived.
    """
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=version_id,
        now=MOMENT,
    )
    return {event.comment_text: event.feedback_id for event in events}


def test_the_layer_lists_the_chain_s_own_issue_keys(env: StoreEnv, tmp_path: Path) -> None:
    """The listing is the chain's own keys, sorted, and it carries no words.

    **The keys are given out of order on purpose**, so a listing that came
    back in the order the rows were written would not pass. **The chain's
    rows carry no time and no sequence**, so there is no chronology to read
    an order out of: an order taken from the rows would be the storage
    engine's and not the chain's, and the same chain would then be two
    listings. **Sorting is an order of the names themselves**, so the same
    set of keys answers the same list however the rows came back.

    **And the comment nobody keyed is not in it.** A key is a person's
    judgement and it is given; a comment with no key is uncategorised, and
    the listing does not turn it into an issue.

    **And the list carries names, not the advisor's words.** The words are
    in the chain, and they are not here: *a key says which problem, not
    what the advisor wrote*.
    """
    chain = _a_chain_with_comments(env, tmp_path)
    first = _the_comments(chain, chain.version_id)
    _the_comments(chain, chain.second_version_id)
    set_issue_key(
        chain.context,
        feedback_id=first["Define the parameter."],
        issue_key="iss-b",
        now=MOMENT,
    )
    set_issue_key(
        chain.context,
        feedback_id=first["Name the core."],
        issue_key="iss-a",
        now=MOMENT,
    )

    keys = chain_layer.read_issue_keys(chain.context, project_id=chain.project_id)

    assert keys == ("iss-a", "iss-b"), (
        f"the listing is the chain's own keys and it is sorted, and it is {keys!r}"
    )
    assert "Give the units." not in keys, (
        "a comment nobody keyed is uncategorised, and the listing does not key it"
    )
    assert "Define the parameter." not in keys, (
        "the listing carries names, and the advisor's words are not names the chain gave"
    )


def _another_project_with_a_key(chain: ChainEnv, *, issue_key: str) -> None:
    """A second project, with a comment of its own under a key of its own.

    **The rows are written directly**, the way the scaffolding writes the
    version graph: the chain's rows are the product's own, and a second
    project is not something the product can be asked to write here.
    """
    session = chain.context.store.session
    session.add(
        PaperProjectRow(
            project_id="proj-2",
            workspace_id="ws-1",
            subject_pseudonym="subject-2",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    session.add(
        PaperVersionRow(
            version_id="ver-9",
            project_id="proj-2",
            source_id=chain.source_id,
            source_content_sha256=None,
            version_label_raw="manuscript.docx",
            stage_candidate="advisor_reviewed",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.commit()
    _raw_insert(
        session,
        feedback_id="fb-other-project",
        project_id="proj-2",
        version_id="ver-9",
        issue_key=issue_key,
    )


def test_the_layer_lists_this_project_s_keys_and_not_another_project_s(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The listing answers about the project it was asked for.

    **Two projects, two chains, two sets of keys.** A listing that carried
    another project's keys would answer a question nobody asked: a reader
    would see an issue that belongs to a manuscript they are not looking at,
    and would look for a trajectory under it that is not there.
    """
    chain = _a_chain_with_comments(env, tmp_path)
    first = _the_comments(chain, chain.version_id)
    set_issue_key(
        chain.context,
        feedback_id=first["Define the parameter."],
        issue_key="iss-mine",
        now=MOMENT,
    )
    _another_project_with_a_key(chain, issue_key="iss-theirs")

    keys = chain_layer.read_issue_keys(chain.context, project_id=chain.project_id)

    assert keys == ("iss-mine",), (
        f"the listing is the project's own keys and not another's, and it is {keys!r}"
    )


def test_the_layer_refuses_a_project_the_chain_does_not_hold(env: StoreEnv, tmp_path: Path) -> None:
    """A project nobody holds is refused by name, not answered with an empty list.

    **An empty list would say the project has no issues**, and that is a
    different fact from *"there is no such project"*. A reader told the
    first would believe the project exists and has nothing to say.
    """
    chain = _a_chain_with_comments(env, tmp_path)
    first = _the_comments(chain, chain.version_id)
    set_issue_key(
        chain.context,
        feedback_id=first["Define the parameter."],
        issue_key="iss-a",
        now=MOMENT,
    )

    with pytest.raises(ApplicationRefusedError) as caught:
        chain_layer.read_issue_keys(chain.context, project_id="proj-nobody-holds")

    assert caught.value.reason is ApplicationRefusal.CHAIN_PROJECT_NOT_FOUND


def test_the_layer_refuses_a_version_that_is_not_the_project_s(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A version outside the project is refused rather than ignored.

    **Ignoring it would answer about a chain that is not this one.** A
    version that is not the project's would widen the answer to a different
    manuscript, and the caller who named it would not know that.

    **And the project's own version is served**, so the refusal is about
    the version that does not belong and not about the listing.
    """
    chain = _a_chain_with_comments(env, tmp_path)
    first = _the_comments(chain, chain.version_id)
    set_issue_key(
        chain.context,
        feedback_id=first["Define the parameter."],
        issue_key="iss-a",
        now=MOMENT,
    )

    with pytest.raises(ApplicationRefusedError) as caught:
        chain_layer.read_issue_keys(
            chain.context,
            project_id=chain.project_id,
            version_ids=("ver-of-another-project",),
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_VERSION_NOT_FOUND

    assert chain_layer.read_issue_keys(
        chain.context,
        project_id=chain.project_id,
        version_ids=(chain.version_id,),
    ) == ("iss-a",)


def test_the_layer_narrows_the_listing_to_the_versions_named(env: StoreEnv, tmp_path: Path) -> None:
    """The versions named narrow the answer, and naming none means the project.

    **A key is a fact about a comment, and a comment belongs to a
    version.** So the version a comment was written against decides whether
    its key is in the answer — and a caller that asks about one round gets
    that round's keys and not the other round's.

    **And naming no version means the whole project**, which is the one
    scope a caller reaches before it knows which versions it wants: a panel
    that lists what there is to look at has the versions from the list, not
    from a question it has not been asked yet.
    """
    chain = _a_chain_with_comments(env, tmp_path)
    first = _the_comments(chain, chain.version_id)
    second = _the_comments(chain, chain.second_version_id)
    set_issue_key(
        chain.context,
        feedback_id=first["Define the parameter."],
        issue_key="iss-first",
        now=MOMENT,
    )
    set_issue_key(
        chain.context,
        feedback_id=second["Report the depth."],
        issue_key="iss-second",
        now=MOMENT,
    )

    whole = chain_layer.read_issue_keys(chain.context, project_id=chain.project_id)
    assert whole == ("iss-first", "iss-second"), (
        f"naming no version means the project's whole chain, and it is {whole!r}"
    )

    narrowed = chain_layer.read_issue_keys(
        chain.context,
        project_id=chain.project_id,
        version_ids=(chain.version_id,),
    )
    assert narrowed == ("iss-first",), (
        f"the version named decides whose keys are listed, and it is {narrowed!r}"
    )


# --------------------------------------------------------------------------- #
# the layer's own comment
# --------------------------------------------------------------------------- #


def test_the_layers_comment_carries_the_anchors_status_and_its_reason(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A caller can tell a placed comment from one the reader could not place.

    **The layer's own comment says which.** The chain's row carries the
    anchor's status and the reason the anchor is unknown, and the
    application layer carries both — so a caller may tell *"the advisor's
    remark was written against this text"* from *"the reader could not
    place the remark in the body"*.

    **And the anchored text alone does not say it.** An unplaced comment
    carries the empty string as its anchored text, and so does a comment
    the reader *did* place on a stretch of the manuscript that holds no
    text: **two different facts, one spelling.** A layer that carried the
    text and left the status behind would make them indistinguishable —
    and the scope of a distilled rule would then quote the empty string
    as though it were the advisor's words.

    **What breaks it:** the layer dropping ``anchor_status`` and
    ``anchor_reason`` on the way out of the store, which is exactly what
    it did before.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("501"), a_comment("502", anchor="none")),
    )
    recorded = _record(chain)
    for event, key in zip(recorded, ("iss-placed", "iss-unplaced"), strict=True):
        set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)

    comments = chain_layer.read_comments(chain.context, issue_keys=("iss-placed", "iss-unplaced"))
    assert len(comments) == 2, "the chain holds the two comments it recorded"
    by_key = {comment.issue_key: comment for comment in comments}

    placed = by_key["iss-placed"]
    assert placed.anchor_status == "resolved", "the placed comment says it was placed"
    assert placed.anchor_reason is None, "a placed anchor has no reason to give"
    assert placed.anchor_text, "the placed comment names the text it sits at"

    unplaced = by_key["iss-unplaced"]
    assert unplaced.anchor_status == "unknown", (
        "the unplaced comment says the reader could not place it"
    )
    assert unplaced.anchor_reason == "the comment carries no range markers", (
        "the reason is the chain's own, not a guess made here"
    )
    assert unplaced.anchor_text == "", "an unplaced comment carries no anchored text"


# --------------------------------------------------------------------------- #
# the reply -- one party's answer to another's objection
# --------------------------------------------------------------------------- #
#
# **The chain holds the mentor's exchange, and a reply is not that
# exchange.** These witnesses are about the fifth thing the feedback work
# order's material holds: a *reviewer's* objection and *the authors'*
# answer, read out of a response document.
#
# **The words in this section are invented.** No material of the owner's
# enters the repository -- not the reviewer's words, not the authors'
# answer, not the lines they cite, and not the file they came from.

#: The paragraphs of the response document the reply witnesses use.
#:
#: **Four paragraphs: two exchanges, each an objection and an answer.**
REPLY_LETTER: tuple[str, ...] = (
    "Comment 1: The unit of the second figure is not stated.",
    "Response 1: We have stated the unit in the caption and in the text.",
    "Comment 2: The third paragraph repeats the first.",
    "Response 2: We have removed the repetition.",
)


@dataclass(frozen=True)
class ReplyEnv:
    """A project holding a manuscript and a response document beside it."""

    chain: ChainEnv
    #: The version of the response document -- the one a reply is read
    #: out of.
    version_id: str
    #: The response document on disk.
    document: Path
    #: Where the documents are built.
    built: Path


def _reply_project(
    env: StoreEnv, tmp_path: Path, *, comments: tuple[Comment, ...] = ()
) -> ReplyEnv:
    """A project holding a manuscript and a response document beside it.

    **The response document is written before the chain is built**, so it
    is ingested with the rest of the material, and it is registered as a
    version of its own -- **because a reply is read out of a document, and
    the document is a material of the project like any other.**

    **The comments are a parameter**, because a settlement that says which
    chain comment a reply is about needs the chain to hold one.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    materials = workspace / "materials"
    materials.mkdir(parents=True)
    built = workspace / "built"
    built.mkdir()
    document = materials / "responses.docx"
    document.write_bytes(
        write_fixture(
            Fixture(name="responses", paragraphs=REPLY_LETTER, purpose="The reply letter."),
            built,
        ).read_bytes()
    )
    chain = build_chain(env.store(), workspace, comments=comments)
    source = next(
        view.source
        for view in list_sources(chain.context)
        if view.source.relative_path.endswith("responses.docx")
    )
    chain.context.store.session.add(
        PaperVersionRow(
            version_id="ver-letter",
            project_id=chain.project_id,
            source_id=str(source.source_id),
            source_content_sha256=str(source.content_sha256),
            version_label_raw="responses.docx",
            stage_candidate="unknown",
            status="resolved",
            created_at=MOMENT,
        )
    )
    chain.context.store.session.commit()
    return ReplyEnv(chain=chain, version_id="ver-letter", document=document, built=built)


def _exchange(
    *,
    objection_paragraph: int = 0,
    objection_party: str = "reviewer",
    answer_paragraph: int = 1,
    answer_party: str = "author",
    pairing_grade: str = "observed",
) -> ReplyExchange:
    """One exchange, named by the two places in the document it was read from.

    **There is no text parameter**, and that is the point: a caller never
    types a reply's words.
    """
    return ReplyExchange(
        objection_paragraph=objection_paragraph,
        objection_party=objection_party,
        answer_paragraph=answer_paragraph,
        answer_party=answer_party,
        pairing_grade=pairing_grade,
    )


def _record_replies(reply_env: ReplyEnv, *exchanges: ReplyExchange) -> tuple[Reply, ...]:
    return record_replies(
        reply_env.chain.context,
        project_id=reply_env.chain.project_id,
        version_id=reply_env.version_id,
        exchanges=exchanges,
        now=MOMENT,
    )


def _raw_reply(session: Session, **overrides: object) -> None:
    """Write a reply row directly, so the schema is what is under test."""
    objection = REPLY_LETTER[0]
    answer = REPLY_LETTER[1]
    values: dict[str, object] = {
        "reply_id": "rp-raw",
        "project_id": "proj-1",
        "version_id": "ver-letter",
        "objection_party": "reviewer",
        "objection_text": objection,
        "objection_text_sha256": hashlib.sha256(objection.encode()).hexdigest(),
        "objection_paragraph": 0,
        "answer_party": "author",
        "answer_text": answer,
        "answer_text_sha256": hashlib.sha256(answer.encode()).hexdigest(),
        "answer_paragraph": 1,
        "pairing_grade": "observed",
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO replies ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


def test_a_reply_row_carries_the_objection_and_the_answer(env: StoreEnv, tmp_path: Path) -> None:
    """A reply is one row holding both halves, and each half names its author.

    **Both halves travel together.** The objection is somebody's words and
    the answer is somebody else's, and the answer is the half that carries
    the reasoning -- so a row that kept only the objection would throw
    away the part a reader came for.

    **And the two halves say who wrote them.** The vocabulary is the
    reply's own: ``reviewer`` and ``author``.

    **What breaks it:** the writer storing one half only, storing the
    halves under the other party's names, or storing a constant instead of
    the document's words.
    """
    reply_env = _reply_project(env, tmp_path)

    recorded = _record_replies(
        reply_env,
        _exchange(),
        _exchange(objection_paragraph=2, answer_paragraph=3),
    )

    assert len(recorded) == 2, "the two exchanges are two rows"
    first = recorded[0]
    assert first.objection_text == REPLY_LETTER[0], "the objection is the document's words"
    assert first.answer_text == REPLY_LETTER[1], "the answer is the document's words"
    assert first.objection_party == "reviewer", "the objection says who wrote it"
    assert first.answer_party == "author", "the answer says who wrote it"
    assert first.objection_paragraph == 0, "the objection says where it was read"
    assert first.answer_paragraph == 1, "the answer says where it was read"
    assert first.version_id == reply_env.version_id, "the reply names the document it was read from"
    assert first.objection_text_sha256 == hashlib.sha256(REPLY_LETTER[0].encode()).hexdigest()
    assert first.answer_text_sha256 == hashlib.sha256(REPLY_LETTER[1].encode()).hexdigest()

    second = recorded[1]
    assert second.objection_text == REPLY_LETTER[2]
    assert second.answer_text == REPLY_LETTER[3]

    # And the listing is in the document's order.
    listed = list_replies(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert [reply.reply_id for reply in listed] == [first.reply_id, second.reply_id], (
        "the exchanges come back in the order the document has them"
    )


def test_a_reply_without_both_halves_is_refused(env: StoreEnv, tmp_path: Path) -> None:
    """One half alone is not a reply, and **the schema** refuses it.

    **The refusal is the database's, not the writer's.** The row is
    written with a raw ``INSERT`` that bypasses the ORM, so what refuses
    it is the constraint and not the code that would have caught it.

    **And "not empty" means "not entirely whitespace."** SQLite's ``trim``
    removes the space character only, so a reply whose half is three
    spaces would pass a naive check and be a reply with nothing in it.

    **What breaks it:** a constraint that lets one half be empty, or one
    that reads emptiness as "not the empty string".
    """
    reply_env = _reply_project(env, tmp_path)
    session = reply_env.chain.context.store.session

    # A reply with no answer.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-no-answer", answer_text="")
    session.rollback()

    # A reply with no objection.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-no-objection", objection_text="")
    session.rollback()

    # A reply whose answer is three spaces.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-blank-answer", answer_text="   ")
    session.rollback()

    # And a hash that is not a hash.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-bad-hash", answer_text_sha256="not-a-hash")
    session.rollback()


def test_the_parties_are_the_replies_own_and_the_chain_cannot_say_them(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The parties are ``reviewer`` and ``author``, and the chain's vocabulary
    cannot say what these two are.

    **The chain's ``actor_kind`` is closed** -- ``student``, ``advisor``,
    ``model``, ``human`` -- and it answers *who acted in the mentor's
    chain*. **A peer reviewer of a submitted manuscript is neither the
    mentor nor the student**, so a value coerced out of that vocabulary
    would be a wrong value. And ``human`` on both halves would be worse
    than wrong: it would say "two people spoke" and be unable to say
    which was which, which is the whole content of a reply.

    **And a reply is one party's answer to *another's* objection**, so a
    row whose two halves are the same party is a monologue, and the schema
    refuses it.

    **What breaks it:** the party vocabulary widened to take the chain's
    values, the "two parties" rule dropped, or the pairing's grade opened.
    """
    reply_env = _reply_project(env, tmp_path)
    session = reply_env.chain.context.store.session

    for party in ("advisor", "student", "model", "human"):
        with pytest.raises(IntegrityError):
            _raw_reply(session, reply_id=f"rp-{party}", objection_party=party)
        session.rollback()

    # The same party on both halves.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-monologue", answer_party="reviewer")
    session.rollback()

    # A pairing graded outside its vocabulary.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-pending", pairing_grade="pending")
    session.rollback()

    # And the paragraphs are in the document's order.
    with pytest.raises(IntegrityError):
        _raw_reply(session, reply_id="rp-backwards", objection_paragraph=3, answer_paragraph=1)
    session.rollback()

    # The writer refuses the same party, before it reaches the database.
    with pytest.raises(ApplicationRefusedError) as caught:
        _record_replies(reply_env, _exchange(objection_party="advisor"))
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID


def test_a_reply_is_recorded_without_a_caller_writing_the_text(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The caller names the two places; the product reads the words.

    **A caller never types a reply's text.** Deciding that one paragraph
    answers another is a judgement, and the project asks a judgement to
    name its decider -- so the caller makes it, and the *words* are a fact
    about the file that the product supplies. **The exchange carries no
    field that could hold a word**, and what the row ends up holding is
    the document's own text, read out of the document.

    **What breaks it:** the writer taking the words from anywhere but the
    document, or the exchange growing a field a caller could type into.
    """
    reply_env = _reply_project(env, tmp_path)

    recorded = _record_replies(reply_env, _exchange())

    letter = read_document(reply_env.document.read_bytes())
    assert recorded[0].objection_text == letter.paragraphs[0], (
        "the objection is the response document's own words"
    )
    assert recorded[0].answer_text == letter.paragraphs[1], (
        "the answer is the response document's own words"
    )
    assert recorded[0].objection_text != letter.paragraphs[1], (
        "the two halves are the document's two paragraphs and not one of them twice"
    )

    named = {field.name for field in fields(ReplyExchange)}
    assert "objection_text" not in named and "answer_text" not in named, (
        f"the exchange carries a field a caller could type a word into: {sorted(named)}"
    )


def test_a_reply_is_a_record_and_not_a_verdict(env: StoreEnv, tmp_path: Path) -> None:
    """The table has no state, no decider and no evidence, and no comment either.

    **A reply is a record of what was said.** ``response_links`` has the
    machinery of a verdict -- a state, a decider, a moment and the
    evidence behind it -- because it answers "did the change answer the
    comment", and that question needs a verdict. **A reply answers
    "what did the author say, and why", and the answer is the content.**
    So the row's columns are exactly the record's, and nothing else.

    **And it holds no reference to the chain's comments.** The objection
    in a reply is not a comment the chain holds -- it names no version,
    and the place it points at is a rendering the corpus does not hold --
    so a row that pointed at one would have to name a version and an
    address the material does not have. **Recording a reply therefore
    creates no comment.**

    **What breaks it:** a column added for a judgement, or the writer
    writing a comment row beside the reply.
    """
    reply_env = _reply_project(env, tmp_path)
    session = reply_env.chain.context.store.session

    assert set(ReplyRow.__table__.columns.keys()) == {
        "reply_id",
        "project_id",
        "version_id",
        "objection_party",
        "objection_text",
        "objection_text_sha256",
        "objection_paragraph",
        "answer_party",
        "answer_text",
        "answer_text_sha256",
        "answer_paragraph",
        "pairing_grade",
        "created_at",
    }, "the table holds the record and nothing else"

    _record_replies(reply_env, _exchange())

    comments = session.scalars(select(FeedbackEventRow)).all()
    assert not comments, "recording a reply creates no comment"


def test_the_reply_names_the_document_it_was_read_from(env: StoreEnv, tmp_path: Path) -> None:
    """The reply's address is into the response document, and nowhere else.

    **The material's own extraction says the addresses do not resolve**:
    the objections in this family address lines in a rendering the corpus
    does not hold. **So a reply names no place in the manuscript under
    review** -- the place the objection points at lives in the
    objection's own words, and there is no column that could hold it.

    **The address the row does carry is the reader's own**: the paragraph
    of the response document each half was read from. **So the reply names
    the document it was read from, and the manuscript under review is a
    different document whose words the row does not hold.**

    **What breaks it:** the reply naming the wrong version, or its words
    coming from somewhere other than the document its version names.
    """
    reply_env = _reply_project(env, tmp_path)

    recorded = _record_replies(reply_env, _exchange())
    reply = recorded[0]

    letter = read_document(reply_env.document.read_bytes())
    manuscript = read_document(reply_env.chain.manuscript.read_bytes())
    assert letter.paragraphs[0] != manuscript.paragraphs[0], (
        "the response document is not the manuscript under review"
    )
    assert reply.objection_text == letter.paragraphs[0], (
        "the reply's words are the response document's, and the reply names that "
        "document as the version it was read from"
    )
    assert reply.version_id != reply_env.chain.version_id, (
        "the reply names the document it was read from, not the manuscript under review"
    )


def test_the_layer_reads_the_replies(env: StoreEnv, tmp_path: Path) -> None:
    """The layer's read returns the exchanges, with both halves and both parties.

    **And a version nobody named is not among them.** The exchanges are
    read by the version they were read from, so a caller that named the
    manuscript under review gets nothing -- and a caller that named the
    response document gets the exchanges and not the words of anything
    else.

    **And they come back in the document's order**, which is the order a
    person reading the response document would meet them in.

    **What breaks it:** the layer dropping a half, dropping a party,
    answering about the versions the caller did not name, or answering in
    whatever order the rows happened to come back.
    """
    reply_env = _reply_project(env, tmp_path)
    recorded = _record_replies(
        reply_env,
        _exchange(),
        _exchange(objection_paragraph=2, answer_paragraph=3),
    )

    replies = chain_layer.read_replies(reply_env.chain.context, version_ids=(reply_env.version_id,))
    assert len(replies) == 2, "the layer reads the exchanges the chain holds"
    read = replies[0]
    assert read.reply_id == recorded[0].reply_id
    assert read.objection_text == REPLY_LETTER[0], "the objection travels out"
    assert read.answer_text == REPLY_LETTER[1], "the answer travels out"
    assert read.objection_party == "reviewer", "the objection's party travels out"
    assert read.answer_party == "author", "the answer's party travels out"

    assert [reply.reply_id for reply in replies] == [
        recorded[0].reply_id,
        recorded[1].reply_id,
    ], "the exchanges come back in the document's order"

    other = chain_layer.read_replies(
        reply_env.chain.context, version_ids=(reply_env.chain.version_id,)
    )
    assert other == (), "a version nobody named an exchange for holds none"


def test_two_exchanges_may_answer_the_same_objection_and_their_order_is_total(
    env: StoreEnv, tmp_path: Path
) -> None:
    """Two exchanges may answer the same objection, and the listing says which is first.

    **The second key is not decoration.** Two exchanges may share an
    objection paragraph -- a reviewer may say one thing and the authors
    answer it in two places -- and **an order that stopped at the
    objection would leave their order to the storage engine's.** The
    listing orders by the answer's paragraph as well, so the answer is
    the same on every machine and is the document's own order.

    **What breaks it:** the tiebreaker dropped, so the two exchanges come
    back in whichever order the rows happened to be written in.
    """
    reply_env = _reply_project(env, tmp_path)
    recorded = _record_replies(
        reply_env,
        _exchange(answer_paragraph=2),
        _exchange(),
    )

    listed = list_replies(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert [reply.reply_id for reply in listed] == [
        recorded[1].reply_id,
        recorded[0].reply_id,
    ], "the exchanges come back in the document's order and not in the order they were written"

    read = chain_layer.read_replies(reply_env.chain.context, version_ids=(reply_env.version_id,))
    assert [reply.reply_id for reply in read] == [
        recorded[1].reply_id,
        recorded[0].reply_id,
    ], "the layer's read says the same thing the listing does"


def test_recording_the_same_exchange_twice_is_the_same_row(env: StoreEnv, tmp_path: Path) -> None:
    """Recording the same document twice is the same rows.

    **A version is a fixed set of bytes**, so the exchange's id is a
    function of the version and the two paragraphs, and a second reading
    finds the rows that are already there. **Recording the same fact
    twice is one fact.**

    **What breaks it:** an id that depends on the order the exchanges
    were read in, so a second reading writes a second row.
    """
    reply_env = _reply_project(env, tmp_path)

    first = _record_replies(reply_env, _exchange())
    second = _record_replies(reply_env, _exchange())

    assert first[0].reply_id == second[0].reply_id, "the same exchange has the same id"
    rows = reply_env.chain.context.store.session.scalars(select(ReplyRow)).all()
    assert len(rows) == 1, "recording the same exchange twice is one exchange"


def test_a_document_that_changed_under_the_name_records_nothing(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A response document whose bytes changed under the name is refused.

    **The version names the document *and* the bytes it was recorded
    with.** A document that has changed under the name is not the one the
    paragraph numbers would name, so nothing is recorded against it --
    and a reply read out of it would be an exchange the file does not
    hold.

    **What breaks it:** the drift check being skipped, so a reply would
    claim the words of a document that is no longer the one that was read.
    """
    reply_env = _reply_project(env, tmp_path)

    reply_env.document.write_bytes(
        write_fixture(
            Fixture(
                name="responses",
                paragraphs=("Comment 1: A different opening.", "Response 1: A different reply."),
                purpose="The reply letter, changed.",
            ),
            reply_env.built,
        ).read_bytes()
    )

    with pytest.raises(ApplicationRefusedError) as caught:
        _record_replies(reply_env, _exchange())
    assert caught.value.reason is ApplicationRefusal.CHAIN_MATERIAL_DRIFTED

    rows = reply_env.chain.context.store.session.scalars(select(ReplyRow)).all()
    assert not rows, "nothing was recorded against the changed document"


def test_a_reply_names_no_paragraph_the_document_does_not_have(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A paragraph number names a place in the document as it reads.

    **A place the document does not have is not a place**, and an
    exchange whose answer comes before its objection is not an exchange
    the document states. **Both are refused before anything is
    written** — and a valid exchange is recorded first, so the refusal has
    something it could have half-written behind it.

    **What breaks it:** the range check dropped, so a reply would carry an
    address that resolves to nothing, or one that puts the answer before
    the question; or the refusal arriving after the first row was added,
    so a later commit would write it.
    """
    reply_env = _reply_project(env, tmp_path)
    session = reply_env.chain.context.store.session

    # A valid exchange first, so the refusals below have something they
    # could have left behind.
    _record_replies(reply_env, _exchange())

    with pytest.raises(ApplicationRefusedError) as caught:
        _record_replies(reply_env, _exchange(objection_paragraph=0, answer_paragraph=99))
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID

    with pytest.raises(ApplicationRefusedError) as caught:
        _record_replies(reply_env, _exchange(objection_paragraph=1, answer_paragraph=0))
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID

    # And the same exchange twice in one call is refused too.
    with pytest.raises(ApplicationRefusedError) as caught:
        _record_replies(reply_env, _exchange(), _exchange())
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID

    rows = session.scalars(select(ReplyRow)).all()
    assert len(rows) == 1, "a refused exchange writes nothing"


# --------------------------------------------------------------------------- #
# the middle rings: the change that was made, and the link put forward
# --------------------------------------------------------------------------- #
#
# **What is under test here.** The chain's second ring (``edit_actions``)
# and its third (``response_links``), and the step that fills the first
# and puts the second forward. **The material the owner's manuscript
# gave is a fact about a file** — every version's revisions carry their
# author's name — and these witnesses are written on **invented** names
# and invented prose, because the repository is public and the paper is
# the owner's.


#: The two names the marked-up manuscript's revisions carry. **They are
#: two people, and the chain does not know which is which** — the roster
#: is the operator's answer to that question, and it is supplied every
#: time the ring is filled.
_ADVISOR_NAME = "Prof. Lin"
_AUTHOR_NAME = "Dr. Chen"

#: The paragraph the marked-up manuscript holds.
_MARKED_PARAGRAPH = "The method estimates the parameter roughly from a single observation."

#: **One change by each of the two people**, so the roster has something
#: to be right about and something to be wrong about.
_TWO_REVISIONS = (
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

#: **The roster.** The operator's answer to *"whose change is this?"*,
#: and **the file's names are the keys and never the values** — the
#: ``actor_id`` is the operator's own handle for the person.
_ROSTER = {
    _ADVISOR_NAME: ActorClaim(actor_kind="advisor", actor_id="advisor-1"),
    _AUTHOR_NAME: ActorClaim(actor_kind="student", actor_id="student-1"),
}

#: A document part with **a change that carries words** and **a cursor
#: left behind**, written by hand because the fixture writer cannot say
#: them.
#:
#: **The empty marker is an ``w:ins`` with no children at all**, under the
#: paragraph mark's run properties: it is what an operation at a point
#: leaves behind, and **it carries no judgement**.
_CURSOR_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
    "<w:body>\n"
    "<w:p>"
    "<w:pPr><w:rPr>"
    '<w:ins w:id="301" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z"/>'
    "</w:rPr></w:pPr>"
    '<w:r><w:t xml:space="preserve">The method estimates the parameter</w:t></w:r>'
    '<w:ins w:id="302" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z">'
    '<w:r><w:t xml:space="preserve">carefully</w:t></w:r>'
    "</w:ins>"
    "</w:p>\n"
    "</w:body>\n"
    "</w:document>\n"
)


@pytest.fixture()
def marked_up(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A workspace whose manuscript carries **two changes by two people**."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"),),
        paragraphs=(_MARKED_PARAGRAPH,),
        revisions=_TWO_REVISIONS,
    )
    record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    return built


def _the_comment_id(chain: ChainEnv) -> str:
    """The one comment the chain holds for this version."""
    return record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )[0].feedback_id


def _the_changes(chain: ChainEnv) -> tuple[str, ...]:
    """The revision-event ids the version's document records.

    **The second version**, because a change is a change in the version
    the edge arrives at: the edge moves from the version the comment was
    written against to the version that carries the change.
    """
    return tuple(
        event.revision_event_id
        for event in record_revision_events(
            chain.context,
            project_id=chain.project_id,
            version_id=chain.second_version_id,
            now=MOMENT,
        )
    )


def _fill_the_second_ring(
    chain: ChainEnv, *, answers: dict[str, str] | None = None
) -> tuple[EditAction, ...]:
    """The step that fills the chain's second ring, with the roster."""
    return record_edits_from_revisions(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        version_edge_id=chain.edge_id,
        actors=_ROSTER,
        answers=answers,
        now=MOMENT,
    )


def _the_edit_for(chain: ChainEnv, change_id: str) -> str:
    """The id of the edit row that records one of the version's changes."""
    return f"ea-{change_id}"


def _a_second_edge_to_the_same_version(chain: ChainEnv) -> None:
    """A second edge arriving at the same version.

    **Written directly**, the way the scaffolding writes the version
    graph: a version that is the child of two edges is a graph the
    chain's own writer cannot be asked to write, and it is the shape
    that makes "the edge the change moved along" a question with more
    than one answer.
    """
    session = chain.context.store.session
    session.add(
        VersionEdgeRow(
            edge_id="edge-2",
            project_id=chain.project_id,
            parent_version_id=chain.version_id,
            child_version_id=chain.second_version_id,
            source="human",
            confidence=1.0,
            evidence_spans=[{"kind": "revision", "text": "revised"}],
            accepted_by="Dr. Chen",
            accepted_at=MOMENT,
            edge_version=1,
            superseded_by=None,
            created_at=MOMENT,
        )
    )
    session.commit()


def test_a_change_is_recorded_from_the_file_and_the_actor_is_the_roster_say(
    marked_up: ChainEnv,
) -> None:
    """One row per tracked change, and the actor is the roster's answer.

    **The chain does not read an actor out of a file.** A name in a
    manuscript is a string somebody typed, and the same person is spelled
    two ways across two drafts — so the roster is the operator's answer,
    supplied every time, and **the file's name is the key the roster is
    looked up by and never the value that is written down**.

    **And one row is one change**, whether or not it answers a comment:
    the column is nullable for exactly that reason, and a student may
    edit for reasons the advisor never wrote down.

    **And the row's id names the change it is.** This table holds no
    text and no address of its own, so the id is what joins a row to
    the revision event it records — and a reader that wants to know
    whose name the file gives the change follows it there.
    """
    recorded = _fill_the_second_ring(marked_up)

    assert len(recorded) == 2, "one row per tracked change"
    by_actor = {action.actor_kind: action for action in recorded}
    assert set(by_actor) == {"advisor", "student"}, "the roster's answer is on the rows"
    assert by_actor["advisor"].actor_id == "advisor-1"
    assert by_actor["student"].actor_id == "student-1"
    assert not any(action.actor_id in (_ADVISOR_NAME, _AUTHOR_NAME) for action in recorded), (
        "the file's name is never copied into the row"
    )
    assert all(action.feedback_id is None for action in recorded), (
        "a change the caller named no comment for answers nothing, and that is not an error"
    )
    assert all(action.grade == "observed" for action in recorded)
    assert all(action.version_edge_id == marked_up.edge_id for action in recorded)
    assert {action.edit_action_id for action in recorded} == {
        _the_edit_for(marked_up, event_id) for event_id in _the_changes(marked_up)
    }, "the row's id names the change it is"


def test_a_name_the_roster_does_not_name_is_refused_and_nothing_is_written(
    marked_up: ChainEnv,
) -> None:
    """A name the roster does not name is refused, and nothing is written.

    **The chain guesses nothing.** A default is how a model's change
    becomes the advisor's, so an author the roster does not name stops
    the whole operation — **before the first row** — and the refusal
    names the author, because "a name nobody placed" is not an answer a
    person can act on.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        record_edits_from_revisions(
            marked_up.context,
            project_id=marked_up.project_id,
            version_id=marked_up.second_version_id,
            version_edge_id=marked_up.edge_id,
            actors={
                _ADVISOR_NAME: ActorClaim(actor_kind="advisor", actor_id="advisor-1"),
            },
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert _AUTHOR_NAME in caught.value.detail, "the refusal names the author"

    rows = marked_up.context.store.session.scalars(select(EditActionRow)).all()
    assert not rows, "a refused roster writes nothing"


def test_an_answer_must_name_a_change_and_a_comment_the_chain_holds(
    marked_up: ChainEnv,
) -> None:
    """The correspondence is the caller's, and it names rows the chain holds.

    **The file does not say which change answers which comment**, and a
    change that answers nothing is not an error — so the caller names the
    correspondence, and **a name the chain does not hold is refused**
    rather than recorded: a change that answers a comment nobody holds
    has answered nothing.
    """
    comment_id = _the_comment_id(marked_up)
    change_id = _the_changes(marked_up)[0]

    with pytest.raises(ApplicationRefusedError) as caught:
        _fill_the_second_ring(marked_up, answers={"rv-nowhere": comment_id})
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID

    with pytest.raises(ApplicationRefusedError) as caught:
        _fill_the_second_ring(marked_up, answers={change_id: "fb-nowhere"})
    assert caught.value.reason is ApplicationRefusal.CHAIN_FEEDBACK_NOT_FOUND

    rows = marked_up.context.store.session.scalars(select(EditActionRow)).all()
    assert not rows, "a refused answer writes nothing"

    recorded = _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    answered = [action for action in recorded if action.feedback_id == comment_id]
    assert len(answered) == 1, "the change names the comment it answers"
    assert answered[0].edit_action_id == _the_edit_for(marked_up, change_id)
    assert len([action for action in recorded if action.feedback_id is None]) == 1, (
        "the other change answers nothing, and that is not an error"
    )


def test_a_cursor_left_behind_is_not_a_change(env: StoreEnv, tmp_path: Path) -> None:
    """Word leaves a mark behind when an operation happens at a point.

    **It is not a change**, and it carries no judgement — so the chain
    records the change and not the mark. **A single total would call the
    mark a change**, and the number a reader draws would be wrong.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(
        env.store(),
        workspace,
        paragraphs=("The method estimates the parameter",),
        revisions=(),
        document_xml=_CURSOR_DOCUMENT,
    )

    recorded = record_edits_from_revisions(
        built.context,
        project_id=built.project_id,
        version_id=built.second_version_id,
        version_edge_id=built.edge_id,
        actors={
            _ADVISOR_NAME: ActorClaim(actor_kind="advisor", actor_id="advisor-1"),
        },
        now=MOMENT,
    )

    assert len(recorded) == 1, "the cursor left behind is not a change"
    assert recorded[0].actor_kind == "advisor"


def test_a_recorded_change_is_not_rewritten_in_place(marked_up: ChainEnv) -> None:
    """The roster is applied when the change is recorded, and not after.

    **A recorded fact is not rewritten in place** — so a roster that
    contradicts the row already written is refused rather than quietly
    ignored, because the chain would otherwise hold two stories about
    one change. **And re-running the same step with the same roster is
    the same rows**, because identity does not depend on insertion order.
    """
    first = _fill_the_second_ring(marked_up)
    again = _fill_the_second_ring(marked_up)
    assert [action.edit_action_id for action in first] == [
        action.edit_action_id for action in again
    ], "recording the same manuscript twice is the same rows"

    with pytest.raises(ApplicationRefusedError) as caught:
        record_edits_from_revisions(
            marked_up.context,
            project_id=marked_up.project_id,
            version_id=marked_up.second_version_id,
            version_edge_id=marked_up.edge_id,
            actors={
                **_ROSTER,
                _AUTHOR_NAME: ActorClaim(actor_kind="advisor", actor_id="advisor-2"),
            },
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "student-1" in caught.value.detail, "the refusal says what the row says"
    assert "advisor-2" in caught.value.detail, "the refusal says what the roster says"

    # **And the correspondence is fixed when the change is recorded.**
    comment_id = _the_comment_id(marked_up)
    change_id = _the_changes(marked_up)[0]
    with pytest.raises(ApplicationRefusedError) as caught:
        _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "None" in caught.value.detail, "the refusal says what the row says"

    # **And the edge the change moved along is fixed too.** A version
    # that is the child of two edges makes "the edge" a question with
    # more than one answer, and the chain will not answer it twice.
    _a_second_edge_to_the_same_version(marked_up)
    with pytest.raises(ApplicationRefusedError) as caught:
        record_edits_from_revisions(
            marked_up.context,
            project_id=marked_up.project_id,
            version_id=marked_up.second_version_id,
            version_edge_id="edge-2",
            actors=_ROSTER,
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "edge-1" in caught.value.detail, "the refusal says what the row says"


def test_a_proposal_is_put_forward_and_decides_nothing(marked_up: ChainEnv) -> None:
    """The operator's step puts a link forward, and decides nothing.

    **A proposal is a pending link**, and the comment stays on the
    unaddressed listing — with the reason that says somebody put it
    forward and nobody has judged it. **The third ring is filled by a
    person or a rule**, and the operation that puts a link forward has
    no way to decide one.

    **And the same correspondence proposed twice is the same link**, so a
    proposal cannot be duplicated under a second name.
    """
    comment_id = _the_comment_id(marked_up)
    change_id = _the_changes(marked_up)[0]
    _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    edit_id = _the_edit_for(marked_up, change_id)

    links = propose_responses(
        marked_up.context,
        proposals=[AnswerProposal(feedback_id=comment_id, edit_action_id=edit_id)],
        proposed_by="model",
        now=MOMENT,
    )

    assert len(links) == 1
    link = links[0]
    assert link.state == "pending", "a proposal decides nothing"
    assert link.grade == "inferred", "a model's candidate is the system's own inference"
    assert link.decided_by == "model", "the row says who put it forward"
    assert link.evidence_refs == (), "a pending link carries no decision"

    unaddressed = list_unaddressed(marked_up.context, project_id=marked_up.project_id)
    assert [item.feedback.feedback_id for item in unaddressed] == [comment_id]
    assert unaddressed[0].reason == "pending", (
        "the reason says a judgement is outstanding, and not that nobody answered"
    )

    again = propose_responses(
        marked_up.context,
        proposals=[AnswerProposal(feedback_id=comment_id, edit_action_id=edit_id)],
        proposed_by="model",
        now=MOMENT,
    )
    assert again[0].response_link_id == link.response_link_id, (
        "the same correspondence proposed twice is the same link"
    )

    # **And a person's proposal is a candidate of its own kind**: it is
    # observed rather than inferred, because nothing has confirmed it
    # and a model's inference and a person's proposal are two different
    # things.
    other_change_id = _the_changes(marked_up)[1]
    other_edit_id = _the_edit_for(marked_up, other_change_id)
    proposed = propose_responses(
        marked_up.context,
        proposals=[AnswerProposal(feedback_id=comment_id, edit_action_id=other_edit_id)],
        proposed_by="user",
        now=MOMENT,
    )
    assert len(proposed) == 1
    assert proposed[0].state == "pending", "a proposal decides nothing"
    assert proposed[0].grade == "observed", "a person's proposal is not an inference"
    assert proposed[0].decided_by == "user", "the row says who put it forward"


def test_a_proposal_about_a_row_the_chain_does_not_hold_is_refused(
    marked_up: ChainEnv,
) -> None:
    """A link is about a comment and a change, and both must be there.

    **A link to a comment nobody holds is a link to nothing**, and a
    refused proposal writes nothing.
    """
    comment_id = _the_comment_id(marked_up)
    change_id = _the_changes(marked_up)[0]
    _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    edit_id = _the_edit_for(marked_up, change_id)

    with pytest.raises(ApplicationRefusedError) as caught:
        propose_responses(
            marked_up.context,
            proposals=[
                AnswerProposal(feedback_id=comment_id, edit_action_id=edit_id),
                AnswerProposal(feedback_id="fb-nowhere", edit_action_id=edit_id),
            ],
            proposed_by="model",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_FEEDBACK_NOT_FOUND

    with pytest.raises(ApplicationRefusedError) as caught:
        propose_responses(
            marked_up.context,
            proposals=[
                AnswerProposal(feedback_id=comment_id, edit_action_id=edit_id),
                AnswerProposal(feedback_id=comment_id, edit_action_id="ea-nowhere"),
            ],
            proposed_by="model",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_EDIT_NOT_FOUND

    rows = marked_up.context.store.session.scalars(select(ResponseLinkRow)).all()
    assert not rows, (
        "a refused proposal writes nothing — the whole plan is checked before the "
        "first link is written, so a good proposal beside a bad one is not written "
        "either"
    )


def test_a_link_does_not_join_two_manuscripts(marked_up: ChainEnv) -> None:
    """A link is about one manuscript.

    **A link across manuscripts joins two archives**, and a chain that
    does that is a chain about nothing: the comment belongs to one
    manuscript and the change to another, and the answer would be a
    claim about a lineage that does not exist.
    """
    comment_id = _the_comment_id(marked_up)
    change_id = _the_changes(marked_up)[0]
    _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    edit_id = _the_edit_for(marked_up, change_id)
    _another_project_with_a_key(marked_up, issue_key="iss-theirs")

    with pytest.raises(ApplicationRefusedError) as caught:
        propose_responses(
            marked_up.context,
            proposals=[AnswerProposal(feedback_id="fb-other-project", edit_action_id=edit_id)],
            proposed_by="model",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "proj-2" in caught.value.detail, "the refusal names the two projects"

    rows = marked_up.context.store.session.scalars(select(ResponseLinkRow)).all()
    assert not rows, "a refused proposal writes nothing"


def test_a_settled_correspondence_is_not_put_forward_again(marked_up: ChainEnv) -> None:
    """A link that has been judged is a question that has an answer.

    **A second proposal about it is a second answer to a question that
    has one**, and the chain refuses it rather than holding the
    correspondence twice over.
    """
    comment_id = _the_comment_id(marked_up)
    change_id = _the_changes(marked_up)[0]
    _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    edit_id = _the_edit_for(marked_up, change_id)
    record_response(
        marked_up.context,
        response_link_id="rl-judged",
        feedback_id=comment_id,
        edit_action_id=edit_id,
        state="addressed",
        grade="human_verified",
        decided_by="user",
        decided_at=MOMENT,
        evidence_refs=("check:1",),
        now=MOMENT,
    )

    with pytest.raises(ApplicationRefusedError) as caught:
        propose_responses(
            marked_up.context,
            proposals=[AnswerProposal(feedback_id=comment_id, edit_action_id=edit_id)],
            proposed_by="model",
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID


def test_a_chain_of_pending_links_serves_no_rule_and_a_judged_one_serves_it(
    marked_up: ChainEnv,
) -> None:
    """What filling the rings changes for the memory, and what it does not.

    **A pending link serves nothing.** The rule is not served and it is
    *reported* — the invalidation is not silent — and the chain says
    which of the two situations it is: the unaddressed listing's reason
    is ``pending`` when somebody has put a link forward and
    ``no_response`` when nobody has.

    **And only a judgement makes the rule servable.** That is the
    design, and it is why the third ring is filled by a person or a
    rule: the operator's step puts the correspondence forward, and the
    memory serves the rule once somebody has decided it.
    """
    comment_id = _the_comment_id(marked_up)
    set_issue_key(
        marked_up.context,
        feedback_id=comment_id,
        issue_key="iss-one",
        now=MOMENT,
    )
    change_id = _the_changes(marked_up)[0]
    _fill_the_second_ring(marked_up, answers={change_id: comment_id})
    edit_id = _the_edit_for(marked_up, change_id)
    rule = propose_rule(
        marked_up.context,
        issue_type="method_and_hypothesis",
        statement="Name the baseline the comparison is against.",
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The advisor's comment on the ablation paragraph.",
        sources=("iss-one",),
        proposed_by="the-mentor",
        now=MOMENT,
    )
    confirmed = confirm_rule(
        marked_up.context,
        rule_id=rule.rule_id,
        confirmed_by="the-second-reader",
        now=MOMENT,
    )
    assert confirmed.state == "confirmed"

    # **Nothing answered: the rule is not served, and it is reported.**
    assert search_rules(marked_up.context) == ()
    assert [item.rule.rule_id for item in invalidated_rules(marked_up.context)] == [rule.rule_id], (
        "the invalidation is not silent"
    )

    # **A proposal put forward, and nobody has judged it: still nothing.**
    propose_responses(
        marked_up.context,
        proposals=[AnswerProposal(feedback_id=comment_id, edit_action_id=edit_id)],
        proposed_by="model",
        now=MOMENT,
    )
    assert search_rules(marked_up.context) == (), "a pending link is not an answer"
    assert [item.rule.rule_id for item in invalidated_rules(marked_up.context)] == [rule.rule_id]

    # **And a judgement is what makes the rule servable.**
    record_response(
        marked_up.context,
        response_link_id="rl-judged",
        feedback_id=comment_id,
        edit_action_id=edit_id,
        state="addressed",
        grade="human_verified",
        decided_by="user",
        decided_at=MOMENT,
        evidence_refs=("check:1",),
        now=MOMENT,
    )
    hits = search_rules(marked_up.context)
    assert [hit.rule.rule_id for hit in hits] == [rule.rule_id]
    assert invalidated_rules(marked_up.context) == ()
    assert list_unaddressed(marked_up.context, project_id=marked_up.project_id) == ()


# --------------------------------------------------------------------------- #
# the edges a change and a comment may not cross
# --------------------------------------------------------------------------- #
#
# **Why these four are here.** The operation holds four guards that say
# a change belongs to one manuscript, on one edge, and may answer only a
# comment of that manuscript. **A guard nobody watches is a sentence
# nobody checks**, and a reviewer who mutates one of them finds the
# whole file green — so each of the four is watched here, by a witness
# that fails when the guard is gone.


def _an_edge_arriving_elsewhere(chain: ChainEnv) -> str:
    """An edge that arrives at the **first** version, not the second.

    **Written directly**, the way the scaffolding writes the version
    graph: a version that is the child of an edge is a question the
    chain's own writer cannot be asked to write, and it is the shape
    that makes "the edge the change moved along" a question with more
    than one answer.
    """
    session = chain.context.store.session
    session.add(
        VersionEdgeRow(
            edge_id="edge-elsewhere",
            project_id=chain.project_id,
            parent_version_id=chain.second_version_id,
            child_version_id=chain.version_id,
            source="human",
            confidence=1.0,
            evidence_spans=[{"kind": "revision", "text": "revised"}],
            accepted_by="Dr. Chen",
            accepted_at=MOMENT,
            edge_version=1,
            superseded_by=None,
            created_at=MOMENT,
        )
    )
    session.commit()
    return "edge-elsewhere"


def test_a_change_must_travel_the_edge_it_is_recorded_on(marked_up: ChainEnv) -> None:
    """A change is a change in the version the edge arrives at.

    **The edge names the version the change is in**, and a change
    recorded against an edge that arrives elsewhere is a change on no
    edge at all — so the operation refuses it rather than writing a
    row the graph cannot place.
    """
    _an_edge_arriving_elsewhere(marked_up)

    with pytest.raises(ApplicationRefusedError) as caught:
        record_edits_from_revisions(
            marked_up.context,
            project_id=marked_up.project_id,
            version_id=marked_up.second_version_id,
            version_edge_id="edge-elsewhere",
            actors=_ROSTER,
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    rows = marked_up.context.store.session.scalars(select(EditActionRow)).all()
    assert not rows, "a refused edge writes nothing"


def test_a_change_must_travel_an_edge_of_its_own_project(marked_up: ChainEnv) -> None:
    """An edge across manuscripts is a claim about a lineage that does not exist.

    **The edge and the change belong to one manuscript**, and a link
    between two of them would join two archives — so the operation
    refuses it and says which two projects it saw.
    """
    _another_project_with_a_key(marked_up, issue_key="iss-theirs")
    session = marked_up.context.store.session
    session.add(
        VersionEdgeRow(
            edge_id="edge-foreign",
            project_id="proj-2",
            parent_version_id="ver-9",
            child_version_id=marked_up.second_version_id,
            source="human",
            confidence=1.0,
            evidence_spans=[{"kind": "revision", "text": "revised"}],
            accepted_by="Dr. Chen",
            accepted_at=MOMENT,
            edge_version=1,
            superseded_by=None,
            created_at=MOMENT,
        )
    )
    session.commit()

    with pytest.raises(ApplicationRefusedError) as caught:
        record_edits_from_revisions(
            marked_up.context,
            project_id=marked_up.project_id,
            version_id=marked_up.second_version_id,
            version_edge_id="edge-foreign",
            actors=_ROSTER,
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "proj-2" in caught.value.detail, "the refusal names the two projects"
    rows = marked_up.context.store.session.scalars(select(EditActionRow)).all()
    assert not rows, "a refused edge writes nothing"


def test_a_change_is_recorded_against_the_project_its_manuscript_belongs_to(
    marked_up: ChainEnv,
) -> None:
    """A change is recorded against the project its manuscript belongs to.

    **The version and the project are checked against each other**, so
    a change cannot be recorded under a project the manuscript is not
    part of — which would put a row in one project's chain that belongs
    to another's.
    """
    _another_project_with_a_key(marked_up, issue_key="iss-theirs")

    with pytest.raises(ApplicationRefusedError) as caught:
        record_edits_from_revisions(
            marked_up.context,
            project_id="proj-2",
            version_id=marked_up.second_version_id,
            version_edge_id=marked_up.edge_id,
            actors=_ROSTER,
            now=MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.CHAIN_VERSION_NOT_FOUND
    rows = marked_up.context.store.session.scalars(select(EditActionRow)).all()
    assert not rows, "a refused project writes nothing"


def test_a_change_in_one_manuscript_cannot_answer_a_comment_in_another(
    marked_up: ChainEnv,
) -> None:
    """A change answers a comment of its own manuscript, and no other.

    **The answer names a comment the chain holds, in this project** —
    a change in one manuscript cannot answer a comment in another, and
    a correspondence that crossed the two would be a claim about a
    lineage that does not exist.
    """
    _another_project_with_a_key(marked_up, issue_key="iss-theirs")
    change_id = _the_changes(marked_up)[0]

    with pytest.raises(ApplicationRefusedError) as caught:
        _fill_the_second_ring(marked_up, answers={change_id: "fb-other-project"})

    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "proj-2" in caught.value.detail, "the refusal names the two projects"
    rows = marked_up.context.store.session.scalars(select(EditActionRow)).all()
    assert not rows, "a refused answer writes nothing"


# --------------------------------------------------------------------------- #
# The settlement: the judgement that an answer settled a reviewer's point     #
#                                                                             #
# The reply is a record of what was said. The settlement is the judgement     #
# over that record -- did the authors' answer settle the point, on what       #
# evidence, and where in the manuscript the change it claims lives -- and     #
# it goes through the same door as ``record_response``: a state other than    #
# ``pending`` needs a decider and the evidence behind it, and a model may     #
# put a settlement forward but may not decide one.                            #
# --------------------------------------------------------------------------- #


def _settle(
    reply_env: ReplyEnv,
    reply_id: str,
    *,
    state: str = "settled",
    settlement_id: str = "st-1",
    grade: str = "observed",
    decided_by: str | None = "user",
    decided_at: datetime | None = MOMENT,
    evidence_refs: tuple[str, ...] = ("the reviewer's own confirmation",),
    claim_terms: tuple[str, ...] = ("single observation",),
    change_version_id: str | None = "ver-1",
    change_paragraph: int | None = 0,
    anchor_status: str = "resolved",
    feedback_id: str | None = None,
    hold_reason: str | None = None,
) -> ReplySettlement:
    """Settle one reply, with a settled judgement's defaults filled in.

    **The defaults are a passing settled judgement** -- a decider, a
    moment, evidence, a claim term the manuscript holds and a resolved
    address -- so a test about a refusal says what is *wrong* by passing
    one argument, and a test about the pending path passes the empty
    judgement's fields and nothing else.
    """
    return settle_reply(
        reply_env.chain.context,
        settlement_id=settlement_id,
        reply_id=reply_id,
        state=state,
        grade=grade,
        decided_by=decided_by,
        decided_at=decided_at,
        evidence_refs=evidence_refs,
        claim_terms=claim_terms,
        change_version_id=change_version_id,
        change_paragraph=change_paragraph,
        anchor_status=anchor_status,
        feedback_id=feedback_id,
        hold_reason=hold_reason,
        now=MOMENT,
    )


def _raw_settlement(session: Session, **overrides: object) -> None:
    """Write a settlement row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "settlement_id": "st-raw",
        "reply_id": "rp-raw",
        "state": "pending",
        "grade": "observed",
        "decided_by": None,
        "decided_at": None,
        "evidence_refs": "[]",
        "claim_terms": "[]",
        "change_version_id": None,
        "change_paragraph": None,
        "anchor_status": "unknown",
        "feedback_id": None,
        "hold_reason": None,
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO reply_settlements ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


def test_a_settlement_whose_claim_the_manuscript_does_not_hold_is_refused_by_name(
    env: StoreEnv, tmp_path: Path
) -> None:
    """An answer that claims what the manuscript does not contain is not done.

    **A settled settlement has found what the answer claims.** The whole
    point of settling is that what the answer claims can be found in the
    manuscript's accepted text, so the operation reads the manuscript and
    checks every claim term before the row is written. **A claim the
    manuscript does not hold is refused, by name** -- the refusal says
    which term was not found -- and never silently accepted.

    **What breaks it:** the findability check short-circuited, a claim
    matched against the response letter instead of the manuscript, or the
    row written and the mismatch reported beside it.
    """
    reply_env = _reply_project(env, tmp_path)
    (reply,) = _record_replies(reply_env, _exchange())

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(reply_env, reply.reply_id, claim_terms=("Gibbs sampler",))

    assert caught.value.reason is ApplicationRefusal.CHAIN_CLAIM_NOT_IN_MANUSCRIPT
    assert "Gibbs sampler" in caught.value.detail, "the refusal names the claim"
    rows = reply_env.chain.context.store.session.scalars(select(ReplySettlementRow)).all()
    assert not rows, "a refused settlement writes nothing"


def test_a_settled_judgement_records_the_terms_it_found_in_the_manuscript(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A settled settlement says what it vouched for, and where it lives.

    **The claim terms are the settlement's evidence**, and they are on the
    row so the judgement can be re-checked when the manuscript changes:
    the terms were found in the version the settlement names, at the
    paragraph it names. **And what ``settled`` says is narrow by design**
    -- the claimed thing is findable in the manuscript. It does not say
    the science was right, and nothing in the settlement carries that.

    **What breaks it:** the terms not stored, or stored without the
    address they were found at.
    """
    reply_env = _reply_project(env, tmp_path)
    (reply,) = _record_replies(reply_env, _exchange())

    settlement = _settle(reply_env, reply.reply_id)

    assert settlement.state == "settled"
    assert settlement.claim_terms == ("single observation",)
    assert settlement.anchor_status == "resolved"
    assert settlement.change_version_id == "ver-1"
    assert settlement.change_paragraph == 0
    row = reply_env.chain.context.store.session.get(ReplySettlementRow, settlement.settlement_id)
    assert row is not None
    assert row.claim_terms == ["single observation"]


def test_an_answer_whose_claim_cannot_be_found_is_held_by_name(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A hold is a judgement, and it names what it is holding for.

    **The refusal is not the only honest path past a claim the manuscript
    does not bear out.** The caller may record the hold instead -- state
    ``held``, and name the claim that could not be found -- and the hold
    is on the listing with its reason, because a hold that says only
    "held" is a hold nobody can lift.

    **What breaks it:** a hold accepted without a reason, a hold kept off
    the listing, or a hold that carried an address it never checked.
    """
    reply_env = _reply_project(env, tmp_path)
    (reply,) = _record_replies(reply_env, _exchange())

    settlement = _settle(
        reply_env,
        reply.reply_id,
        state="held",
        claim_terms=(),
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
        hold_reason=(
            "the manuscript's accepted text names no Gibbs sampler; the claim "
            "may land in a later revision"
        ),
    )

    assert settlement.state == "held"
    assert settlement.hold_reason is not None
    assert "Gibbs sampler" in settlement.hold_reason
    assert settlement.anchor_status == "unknown", "a hold that found nothing places nothing"
    listed = list_unsettled_replies(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert [(item.reply.reply_id, item.reason) for item in listed] == [(reply.reply_id, "held")]


def test_an_unjudged_reply_stays_on_the_unsettled_listing(env: StoreEnv, tmp_path: Path) -> None:
    """An answer that was never judged does not make the point answered.

    **The answer's words are on the record from the moment the reply is
    recorded** -- and the point is still open, because nothing has judged
    whether what the authors said settled it. A reply the store holds no
    settlement for is listed as ``unjudged``; a reply whose settlement is
    pending is listed as ``pending``; **and only a settled settlement
    keeps a reply off the listing.**

    **What breaks it:** the listing treating the answer's presence as an
    answer, or dropping a reply whose judgement is still pending.
    """
    reply_env = _reply_project(env, tmp_path)
    (reply,) = _record_replies(reply_env, _exchange())
    listing = list_unsettled_replies(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert [(item.reply.reply_id, item.reason) for item in listing] == [
        (reply.reply_id, "unjudged")
    ]

    _settle(
        reply_env,
        reply.reply_id,
        state="pending",
        grade="observed",
        decided_by="user",
        decided_at=None,
        evidence_refs=(),
        claim_terms=(),
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
    )
    listing = list_unsettled_replies(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert [(item.reply.reply_id, item.reason) for item in listing] == [
        (reply.reply_id, "pending")
    ], "the answer is on the record and the point is still open"

    _settle(reply_env, reply.reply_id)
    listing = list_unsettled_replies(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert listing == (), "a settled point is not on the unsettled listing"


def test_a_settlement_places_the_change_or_says_it_could_not(env: StoreEnv, tmp_path: Path) -> None:
    """A review point is located in the response and, if it can be, in the change.

    **The reply already names a place in the response document.** The
    settlement's own address is the other one: where in the manuscript
    the change the answer claims lives. A settlement either places it --
    ``resolved``, with the version and the paragraph -- or says
    ``unknown``, and **a missing address is a value, never a guess**: a
    status and an address that disagree are refused, and an address the
    manuscript does not have is refused.

    **What breaks it:** a ``resolved`` that names no place, an ``unknown``
    that names one anyway, or a paragraph number beyond the manuscript's
    own.
    """
    reply_env = _reply_project(env, tmp_path)
    (reply,) = _record_replies(reply_env, _exchange())

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(
            reply_env,
            reply.reply_id,
            change_version_id=None,
            change_paragraph=None,
            anchor_status="resolved",
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "resolved" in caught.value.detail
    rows = reply_env.chain.context.store.session.scalars(select(ReplySettlementRow)).all()
    assert not rows, "the first attempt wrote nothing"

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(
            reply_env,
            reply.reply_id,
            change_paragraph=None,
            anchor_status="unknown",
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "names a place for it anyway" in caught.value.detail, (
        "the refusal says the status and the address disagree"
    )
    rows = reply_env.chain.context.store.session.scalars(select(ReplySettlementRow)).all()
    assert not rows, "the second attempt wrote nothing"

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(reply_env, reply.reply_id, change_paragraph=7)
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "7" in caught.value.detail, "the refusal names the paragraph it saw"

    settlement = _settle(
        reply_env,
        reply.reply_id,
        state="held",
        claim_terms=(),
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
        hold_reason="the change could not be placed; the letter names no section",
    )
    assert settlement.anchor_status == "unknown", (
        "the explicit unknown is on the row, not a guess in its place"
    )


def test_the_store_refuses_a_settlement_the_schema_forbids(env: StoreEnv, tmp_path: Path) -> None:
    """Every row the schema refuses is refused by the schema.

    **A status anybody can set is not a status**, and neither is an
    address, a claim or a hold that exists only by the writer's
    discretion. So the forbidden rows are written raw -- through the
    database, past every check the application layer makes -- and the
    database refuses them, and leaves nothing behind.

    **What breaks it:** a constraint dropped from the model or from the
    migration, or one written into one and not the other -- which is what
    the parity test holds together, and what a text comparison alone
    cannot catch.
    """
    reply_env = _reply_project(env, tmp_path)
    session = reply_env.chain.context.store.session
    _raw_reply(session)

    def refuses(**overrides: object) -> None:
        """One forbidden row: the store refuses it and holds no trace."""
        with pytest.raises(IntegrityError):
            _raw_settlement(session, **overrides)
        session.rollback()
        rows = session.scalars(select(ReplySettlementRow)).all()
        assert not rows, "a refused row leaves nothing behind"

    # A settled settlement that names no claim it checked.
    refuses(
        state="settled",
        grade="human_verified",
        decided_by="user",
        decided_at=MOMENT.isoformat(),
        evidence_refs='["the reviewer\'s own confirmation"]',
        claim_terms="[]",
        change_version_id="ver-1",
        change_paragraph=0,
        anchor_status="resolved",
    )
    # A settled settlement with no place in the manuscript.
    refuses(
        state="settled",
        grade="human_verified",
        decided_by="user",
        decided_at=MOMENT.isoformat(),
        evidence_refs='["the reviewer\'s own confirmation"]',
        claim_terms='["single observation"]',
        change_version_id=None,
        change_paragraph=None,
        anchor_status="resolved",
    )
    # An unknown that names a place anyway.
    refuses(
        state="pending",
        grade="observed",
        decided_by=None,
        decided_at=None,
        evidence_refs="[]",
        claim_terms="[]",
        change_version_id="ver-1",
        change_paragraph=0,
        anchor_status="unknown",
    )
    # A hold that names nothing.
    refuses(
        state="held",
        grade="human_verified",
        decided_by="user",
        decided_at=MOMENT.isoformat(),
        evidence_refs='["the reviewer\'s own confirmation"]',
        claim_terms="[]",
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
        hold_reason=None,
    )
    # A judgement that names no decider.
    refuses(
        state="unresolved",
        grade="human_verified",
        decided_by=None,
        decided_at=None,
        evidence_refs="[]",
        claim_terms="[]",
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
    )
    # A model settling a point.
    refuses(
        state="settled",
        grade="observed",
        decided_by="model",
        decided_at=MOMENT.isoformat(),
        evidence_refs='["the model\'s own account"]',
        claim_terms='["single observation"]',
        change_version_id="ver-1",
        change_paragraph=0,
        anchor_status="resolved",
    )
    # A pending settlement carrying a decision's trappings.
    refuses(
        state="pending",
        grade="observed",
        decided_by=None,
        decided_at=MOMENT.isoformat(),
        evidence_refs='["the reviewer\'s own confirmation"]',
        claim_terms="[]",
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
    )
    # An anchor status outside its vocabulary.
    refuses(
        state="pending",
        grade="observed",
        decided_by=None,
        decided_at=None,
        evidence_refs="[]",
        claim_terms="[]",
        change_version_id=None,
        change_paragraph=None,
        anchor_status="placed",
    )
    # A state outside its vocabulary.
    refuses(
        state="won",
        grade="observed",
        decided_by=None,
        decided_at=None,
        evidence_refs="[]",
        claim_terms="[]",
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
    )
    # A second judgement over the same reply.
    _raw_settlement(session)
    with pytest.raises(IntegrityError):
        _raw_settlement(session, settlement_id="st-second")
    session.rollback()
    rows = session.scalars(select(ReplySettlementRow)).all()
    assert [row.settlement_id for row in rows] == ["st-raw"], (
        "one reply holds one settlement, and the store says so"
    )


def test_a_reply_that_has_already_been_judged_is_not_judged_again(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A judgement is a fact, and the store holds no revisions of facts.

    **One point, one judgement.** A reply that stands judged is refused
    rather than judged again, and a pending settlement is completed by
    the judgement that decides it -- under the name it was put forward
    with, and no other.

    **What breaks it:** a second settlement row over the same reply, or a
    judgement that renames the settlement it completes.
    """
    reply_env = _reply_project(env, tmp_path)
    (first, second) = _record_replies(
        reply_env,
        _exchange(objection_paragraph=0, answer_paragraph=1),
        _exchange(objection_paragraph=2, answer_paragraph=3),
    )

    _settle(reply_env, first.reply_id)
    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(
            reply_env,
            first.reply_id,
            state="unresolved",
            settlement_id="st-again",
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_SETTLEMENT_ALREADY_DECIDED
    rows = reply_env.chain.context.store.session.scalars(select(ReplySettlementRow)).all()
    assert len(rows) == 1, "the refused judgement wrote no second row"

    _settle(
        reply_env,
        second.reply_id,
        state="pending",
        grade="observed",
        decided_by="user",
        decided_at=None,
        evidence_refs=(),
        claim_terms=(),
        change_version_id=None,
        change_paragraph=None,
        anchor_status="unknown",
        settlement_id="st-forward",
    )
    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(
            reply_env,
            second.reply_id,
            settlement_id="st-elsewhere",
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "st-forward" in caught.value.detail, (
        "the refusal names the settlement the record already holds"
    )
    rows = reply_env.chain.context.store.session.scalars(select(ReplySettlementRow)).all()
    assert {row.settlement_id for row in rows} == {"st-1", "st-forward"}


def _a_judged_chain(reply_env: ReplyEnv, *, states: tuple[str, ...]) -> str:
    """The chain's judgement on one comment, and the reply beside it.

    **The chain's judgement is real rows**, not a shorthand: a comment
    the advisor wrote, a change made in answer to it, and one link per
    state -- each link on an edit of the chain's own, because a state
    that no change backs is a status and not a judgement.
    """
    chain = reply_env.chain
    session = chain.context.store.session
    (event,) = _record(chain)
    for index, state in enumerate(states):
        edit_action_id = f"ea-{index}"
        session.add(
            EditActionRow(
                edit_action_id=edit_action_id,
                feedback_id=event.feedback_id,
                version_edge_id=chain.edge_id,
                actor_kind="student",
                actor_id=None,
                grade="observed",
                created_at=MOMENT,
            )
        )
        session.commit()
        record_response(
            chain.context,
            response_link_id=f"rl-{index}",
            feedback_id=event.feedback_id,
            edit_action_id=edit_action_id,
            state=state,
            grade="human_verified",
            decided_by="user",
            decided_at=MOMENT,
            evidence_refs=("the mentor's own account",),
            now=MOMENT,
        )
    return event.feedback_id


def test_a_disagreement_between_the_chain_and_a_settlement_is_shown_as_two_sides(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A conflict between the mentor's view and the settlement shows both.

    **The chain's judgement on a comment and the settlement's judgement on
    the reply about the same point may disagree**, and the product reports
    both rather than picking the newer: the listing joins every state the
    chain holds for the comment the settlement names, and a reader asking
    "does the chain agree?" gets the whole of the chain's side.

    **What breaks it:** the listing keeping only the newest link's state
    -- which would be deciding a disagreement by recency -- or dropping
    the chain's side when the two disagree.
    """
    reply_env = _reply_project(env, tmp_path, comments=(a_comment("201"),))
    (reply,) = _record_replies(reply_env, _exchange())
    feedback_id = _a_judged_chain(reply_env, states=("not_addressed", "addressed"))

    settlement = _settle(reply_env, reply.reply_id, feedback_id=feedback_id)
    assert settlement.state == "settled"
    listed = list_reply_settlements(reply_env.chain.context, project_id=reply_env.chain.project_id)
    assert [(row.settlement_id, row.state) for row in listed] == [
        (settlement.settlement_id, "settled")
    ]
    assert len(listed[0].chain_states) == 2, (
        "both of the chain's verdicts are shown, and the newer one is not picked"
    )
    assert set(listed[0].chain_states) == {"not_addressed", "addressed"}, (
        "the chain's side is on the listing beside the settlement's, whole"
    )


def test_a_judgement_the_door_refuses_never_reaches_the_store(
    env: StoreEnv, tmp_path: Path
) -> None:
    """The door refuses an undisciplined judgement before the store sees it.

    **The schema holds the same line the operation does** -- a judgement
    with no decider and no evidence, a model's verdict, a hold with no
    reason are all refused by the database too -- **and the operation
    refuses them first, saying why**, because a refusal that reaches a
    caller as an ``IntegrityError`` is a refusal nobody can act on.

    **What breaks it:** the door's own discipline checks short-circuited
    and the refusal left to the schema -- which would still refuse, but
    would say so in SQLite's words and not the product's.
    """
    reply_env = _reply_project(env, tmp_path)
    (reply,) = _record_replies(reply_env, _exchange())

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(
            reply_env,
            reply.reply_id,
            decided_by=None,
            decided_at=None,
            evidence_refs=(),
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_SETTLEMENT_NEEDS_EVIDENCE
    rows = reply_env.chain.context.store.session.scalars(select(ReplySettlementRow)).all()
    assert not rows, "the refused judgement wrote nothing"

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(reply_env, reply.reply_id, decided_by="model", grade="inferred")
    assert caught.value.reason is ApplicationRefusal.CHAIN_SETTLEMENT_MAY_NOT_BE_DECIDED_BY_A_MODEL

    with pytest.raises(ApplicationRefusedError) as caught:
        _settle(
            reply_env,
            reply.reply_id,
            state="held",
            claim_terms=(),
            change_version_id=None,
            change_paragraph=None,
            anchor_status="unknown",
            evidence_refs=("the reviewer's own confirmation",),
            hold_reason=None,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "nobody can lift" in caught.value.detail, (
        "the hold's refusal says why a hold names what it holds"
    )


# --------------------------------------------------------------------------- #
# A8  the anchor that is a position     a zero-width range is recorded as an
#                                unknown anchor with its reason, and the
#                                empty-string digest is never an integrity
#                                value for anchored text
# --------------------------------------------------------------------------- #

#: The digest of the empty string, which is what a resolved claim over no
#: text used to carry as its integrity value.
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()

#: A document part whose comment's range markers sit **inside** the
#: ``w:del`` of the words they cover -- the shape Word writes when a
#: commented-upon span is later deleted, and the shape the pilot's three
#: reader-defect rows carried. Written by hand because the fixture writer
#: places markers beside revisions, never inside one.
_DELETION_ANCHOR_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
    "<w:body>\n"
    "<w:p>"
    '<w:r><w:t xml:space="preserve">Lead in. </w:t></w:r>'
    '<w:del w:id="900" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z">'
    '<w:commentRangeStart w:id="201"/>'
    '<w:r><w:delText xml:space="preserve">removed span</w:delText></w:r>'
    '<w:commentRangeEnd w:id="201"/>'
    '<w:r><w:commentReference w:id="201"/></w:r>'
    "</w:del>"
    '<w:r><w:t xml:space="preserve">Tail.</w:t></w:r>'
    "</w:p>\n"
    "</w:body>\n"
    "</w:document>\n"
)

#: A document part whose comment's range **closes where it opens** -- the
#: reviewer commented on the place, not on words.
_POINT_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
    "<w:body>\n"
    "<w:p>"
    '<w:r><w:t xml:space="preserve">Lead in. </w:t></w:r>'
    '<w:commentRangeStart w:id="201"/>'
    '<w:commentRangeEnd w:id="201"/>'
    '<w:r><w:commentReference w:id="201"/></w:r>'
    '<w:r><w:t xml:space="preserve">Tail.</w:t></w:r>'
    "</w:p>\n"
    "</w:body>\n"
    "</w:document>\n"
)


def test_the_words_a_deletion_covered_are_anchored(env: StoreEnv, tmp_path: Path) -> None:
    """A comment inside a deletion anchors the words the deletion removed.

    The deleted text is baseline text -- the rejected view is the
    manuscript as it read before the change -- so the reader that walks a
    deletion from its start records the markers where the words sit. The
    pre-fix reader entered the deletion at the offset past its whole
    width, recorded both markers there, sliced the empty string and
    hashed it: the pilot's three ``resolved`` rows with no anchored text,
    whose files held 66, 66 and 10 baseline characters, were this shape.

    **What breaks it:** reverting the walk. The row then stores an empty
    anchored text, a digest of nothing, and this test fails on the text.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"),),
        paragraphs=("The method estimates the parameter",),
        document_xml=_DELETION_ANCHOR_DOCUMENT,
    )
    (event,) = _record(built)
    assert event.anchor_status == "resolved"
    assert event.anchor_text == "removed span"
    assert event.anchor_text_sha256 == hashlib.sha256(b"removed span").hexdigest()
    assert event.anchor_text_sha256 != _EMPTY_SHA256
    assert (event.anchor_start, event.anchor_end) == (
        len("Lead in. "),
        len("Lead in. ") + len("removed span"),
    )
    assert anchor_state(built.context, feedback_id=event.feedback_id, now=MOMENT) == "fresh"


def test_a_position_anchor_is_recorded_and_never_fresh(env: StoreEnv, tmp_path: Path) -> None:
    """A zero-width range is a position, and the row says so.

    The reader reports the range that closes where it opens as an unknown
    anchor with its reason; the row keeps the comment's body, its author
    and the paragraph the reader found, and loses nothing but the claim.
    **The row that used to store the digest of the empty string as the
    integrity value of a resolved passage is the row this witness
    forbids**: ``anchor_state`` answers ``unanchored`` for it, never
    ``fresh``.

    **What breaks it:** a reader (or a door) that stores the zero-width
    range as ``resolved`` again -- the row then claims anchored text, the
    digest is the digest of nothing, and the status assertion fails.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"),),
        paragraphs=("The method estimates the parameter",),
        document_xml=_POINT_DOCUMENT,
    )
    (event,) = _record(built)
    assert event.anchor_status == "unknown"
    assert event.anchor_reason == "the comment's range is a position, not a passage of text"
    assert event.anchor_paragraph == 0, "the place the reader found is kept"
    assert event.anchor_start is None
    assert event.anchor_end is None
    assert event.anchor_text == ""
    assert event.comment_text == a_comment("201").text, "the comment is not lost"
    assert anchor_state(built.context, feedback_id=event.feedback_id, now=MOMENT) == "unanchored"


def test_a_row_claiming_an_empty_text_is_never_fresh(env: StoreEnv, tmp_path: Path) -> None:
    """A resolved row whose anchored text is empty cannot be confirmed.

    Stores recorded before the fix hold rows shaped ``resolved`` with an
    empty anchored text and the digest of the empty string. **Empty
    matching empty is the false ``fresh``**: whatever the file now reads,
    there are no words to still be there, so the row is reported stale
    until it is re-derived against the file. The manuscript here carries a
    *point* comment, so a re-read of the file also covers no words -- the
    case where the two empty strings hash the same and only the guards
    stand between the row and a false ``fresh``. A mutation that returns
    ``fresh`` whenever a digest is present fails here.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    built = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"),),
        paragraphs=("The method estimates the parameter",),
        document_xml=_POINT_DOCUMENT,
    )
    (event,) = _record(built)
    session = built.context.store.session
    row = session.get(FeedbackEventRow, event.feedback_id)
    assert row is not None
    # The shape a store recorded before the fix: a resolved claim, no
    # anchored words, and the digest of the empty string as its
    # integrity value.
    row.anchor_status = "resolved"
    row.anchor_reason = None
    row.anchor_paragraph = 0
    row.anchor_start = len("Lead in. ")
    row.anchor_end = len("Lead in. ")
    row.anchor_text = ""
    row.anchor_text_sha256 = _EMPTY_SHA256
    session.commit()
    assert anchor_state(built.context, feedback_id=event.feedback_id, now=MOMENT) == "stale"


def test_the_door_refuses_a_resolved_anchor_that_covers_no_words(
    chain: ChainEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The door refuses a resolved anchor that covers no words.

    **The refusal is the seam, not the common path.** The reader reports
    a position as an unknown anchor, so a ``resolved``-with-no-text
    anchor reaching the door means a reader regression or a hand-built
    claim. It is refused rather than stored with the digest of the empty
    string as its integrity value, and nothing is written: a claim the
    file does not back is not a comment the chain holds.
    """
    fabricated = RevisionDocument(
        revisions=(),
        comments=(
            CommentEvent(
                comment_id="201",
                author="Prof. Lin",
                date=datetime(2026, 3, 2, 9, 30, tzinfo=UTC),
                text="Reword this.",
                locator=DocxLocator(
                    part="word/document.xml",
                    element_path="/w:document[1]/w:body[1]/w:p[1]",
                    view="accepted",
                    char_start=0,
                    char_end=12,
                ),
                anchor=CommentAnchor(
                    status="resolved",
                    reason=None,
                    paragraph=0,
                    start=0,
                    end=0,
                    text="",
                ),
                text_sha256=hashlib.sha256(b"Reword this.").hexdigest(),
            ),
        ),
        accepted_text="The method estimates the parameter",
        rejected_text="The method estimates the parameter",
        paragraphs=("The method estimates the parameter",),
        baseline_paragraphs=("The method estimates the parameter",),
        problems=(),
    )
    monkeypatch.setattr("labcairn.papers.feedback.read_document", lambda data: fabricated)
    with pytest.raises(ApplicationRefusedError) as caught:
        _record(chain)
    assert caught.value.reason == ApplicationRefusal.CHAIN_ANCHOR_RESOLVED_WITHOUT_TEXT
    assert CHAIN_REFUSALS[ChainRefusal.ANCHOR_RESOLVED_WITHOUT_TEXT] is caught.value.reason, (
        "the door's refusal is the new member's own name"
    )
    rows = chain.context.store.session.scalars(select(FeedbackEventRow)).all()
    assert rows == [], "a refused claim writes nothing"
