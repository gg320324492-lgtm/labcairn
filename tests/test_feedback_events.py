"""The feedback row: a comment found in a manuscript, and its two addresses.

**What is under test.** LC-P2-09 T01: ``feedback_events``, and the
acceptance clauses that carry it.

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
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from feedback_chain_fixtures import (
    MOMENT,
    ChainEnv,
    a_comment,
    build_chain,
)
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.refusal import (
    CHAIN_REFUSALS,
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refusal_name,
)
from labcairn.db.models import FeedbackEventRow
from labcairn.material.ooxml import read_document
from labcairn.papers.chain import ChainRefusal
from labcairn.papers.feedback import (
    FeedbackEvent,
    anchor_state,
    list_feedback_events,
    record_feedback,
    set_issue_key,
)

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
