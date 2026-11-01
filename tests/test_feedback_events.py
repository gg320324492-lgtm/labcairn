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
from pathlib import Path

import pytest
from docx_fixtures import Fixture, write_fixture
from feedback_chain_fixtures import (
    MOMENT,
    ChainEnv,
    a_comment,
    build_chain,
)
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import chain as chain_layer
from labcairn.application.refusal import (
    CHAIN_REFUSALS,
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refusal_name,
)
from labcairn.application.sources import list_sources
from labcairn.db.models import (
    FeedbackEventRow,
    PaperProjectRow,
    PaperVersionRow,
    ReplyRow,
)
from labcairn.material.ooxml import read_document
from labcairn.papers.chain import ChainRefusal
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
    list_replies,
    record_replies,
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


def _reply_project(env: StoreEnv, tmp_path: Path) -> ReplyEnv:
    """A project holding a manuscript and a response document beside it.

    **The response document is written before the chain is built**, so it
    is ingested with the rest of the material, and it is registered as a
    version of its own -- **because a reply is read out of a document, and
    the document is a material of the project like any other.**
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
    chain = build_chain(env.store(), workspace)
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
