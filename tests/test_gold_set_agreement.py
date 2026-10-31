"""The agreement is computed from the manifest, and it names its denominator.

**What this file watches.** LC-P2-10's T03 asks for one number -- how far two
annotators agreed -- and **a number nobody can read is worse than no
number**. So the report carries two things: the agreement itself, and the
denominator it was computed over, named in words.

**The denominator is the number of items both annotators labelled.** Not the
number of items in the manifest, and not the number either annotator
labelled. The three are the same number whenever every item carries two
readings, and the report says which one it is, because the day an item
carries one reading the other two would differ -- and the report refuses
that manifest rather than quietly counting it.

**``None`` is not zero.** Zero says "they disagreed about everything";
``None`` says "there was nothing to compare". A report that answered zero
where the truth is "nothing to compare" would report a catastrophe that did
not happen, and a reader of the number could not tell the two apart.

**``UNKNOWN`` is in the distribution.** It is an answer the annotator chose,
and a distribution that drops the honest ones reports more agreement than
the two readers had.

**And the arbiter's row is not the input.** The resolution is recorded
beside the two readings; a report computed from it would be a statement
about the arbiter alone, and the disagreement it settles is the very thing
the number is computed from.

**And a moment names an offset.** Two annotators in two places write the
same clock time and mean two different moments, so a moment with no offset
cannot be compared with the other reader's, and the manifest refuses it.

**Why the manifests here are built in this file.** The manifest in the tree
is written by a person (T06) and is still being filled in, so a witness that
read it would be a witness on whatever happened to be in the file that week.
These manifests are built here, against the contract module's own schema, so
the numbers below are the numbers the contract produces for a manifest of a
known shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from labcairn.papers.gold_manifest import (
    Agreement,
    LabelAgreement,
    agreement,
    unknown_share,
    validate_manifest,
)
from labcairn.papers.labels import UNKNOWN

pytestmark = pytest.mark.unit

#: The project every item of every fixture belongs to, and the fixture it reads.
_PROJECT = "project-alpha"
_FIXTURE = "papers-gold/one.docx"

#: The six views a report carries: two addresses, three axes each.
_EXPECTED_VIEWS = (
    "comment_address.issue_kind",
    "comment_address.response_state",
    "comment_address.assessment_outcome",
    "body_address.issue_kind",
    "body_address.response_state",
    "body_address.assessment_outcome",
)

#: How many items the corpus holds, and how many readings each of them has.
_ITEMS = 7
_READINGS_PER_ITEM = 2


def _address(issue_kind: str, response_state: str, assessment_outcome: str) -> dict[str, str]:
    """One address's three labels, as the manifest spells them."""
    return {
        "issue_kind": issue_kind,
        "response_state": response_state,
        "assessment_outcome": assessment_outcome,
    }


def _reading(
    annotator_id: str,
    comment: dict[str, str],
    body: dict[str, str],
    *,
    at: str,
) -> dict[str, Any]:
    """One annotator's reading of one item: both of its addresses."""
    return {
        "annotator_id": annotator_id,
        "annotated_at": at,
        "comment_address": comment,
        "body_address": body,
    }


def _resolution(
    comment: dict[str, str],
    body: dict[str, str],
    *,
    arbiter_id: str = "arbiter-one",
) -> dict[str, Any]:
    """The arbiter's answer, as a row of its own."""
    return {
        "arbiter_id": arbiter_id,
        "resolved_at": "2026-10-03T08:00:00+00:00",
        "comment_address": comment,
        "body_address": body,
    }


def _item(
    item_id: str,
    first_comment: dict[str, str],
    first_body: dict[str, str],
    second_comment: dict[str, str],
    second_body: dict[str, str],
    *,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One item: two independent readings of its two addresses.

    **The two annotators are different people.** One person reading twice is
    one reading, and the agreement over it would be a statement about that
    person's consistency on a single pass.
    """
    return {
        "item_id": item_id,
        "project_id": _PROJECT,
        "version_id": "version-1",
        "feedback_id": f"feedback-{item_id}",
        "fixture": _FIXTURE,
        "comment_id": f"comment-{item_id}",
        "paragraph": 3,
        "start": 10,
        "end": 40,
        "annotations": [
            _reading(
                "annotator-one",
                first_comment,
                first_body,
                at="2026-10-02T09:00:00+00:00",
            ),
            _reading(
                "annotator-two",
                second_comment,
                second_body,
                at="2026-10-02T11:30:00+00:00",
            ),
        ],
        "resolution": _resolution(first_comment, first_body) if resolution is None else resolution,
    }


def _corpus_items(
    *,
    item_two_issue_kind: str = "figures",
    doubt_issue_kind: str = UNKNOWN,
    doubt_response_state: str = UNKNOWN,
    resolution: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """The seven-item corpus the tests here read.

    **Seven items, and each one carries a different kind of reading.** One
    item the two annotators read identically; one that differs on a single
    axis of the *comment* address; one that differs on the issue kind of
    *both* addresses; one that differs on the comment address's response
    state; two that differ on the *body* address; and one where both
    annotators answered ``unknown``.

    **And the six view counts come out all different within each address** --
    5, 6, 7 for the comment address and 6, 5, 4 for the body address. That
    is the point of the spread: a report that counted the comment address's
    numbers under the body address's names, or one axis's numbers under
    another axis's name, would have to move a number the corpus says is in
    a different place, and a corpus whose counts all happened to be equal
    would let that mistake through.

    **The knobs are the labels that vary.** ``item_two_issue_kind`` is the
    label annotator two gave item two's comment address, and the two
    ``doubt_*`` labels are what the honest doubts are called -- so a test
    can change one label of the corpus and watch the numbers move.
    """
    return [
        # The two read exactly the same.
        _item(
            "item-identical",
            _address("data_quality", "addressed", "established"),
            _address("figures", "pending", "not_established"),
            _address("data_quality", "addressed", "established"),
            _address("figures", "pending", "not_established"),
            resolution=resolution,
        ),
        # The comment address's issue kind differs; the body address is the same.
        _item(
            "item-comment-issue",
            _address("data_quality", "addressed", "established"),
            _address("sources", "addressed", "established"),
            _address(item_two_issue_kind, "addressed", "established"),
            _address("sources", "addressed", "established"),
            resolution=resolution,
        ),
        # Both addresses' issue kinds differ, and nothing else does.
        _item(
            "item-both-addresses",
            _address("data_quality", "pending", "not_established"),
            _address("figures", "pending", "not_established"),
            _address("method_and_hypothesis", "pending", "not_established"),
            _address("sources", "pending", "not_established"),
            resolution=resolution,
        ),
        # The comment address's response state differs, and the body address's
        # assessment outcome differs with it.
        _item(
            "item-comment-response",
            _address("data_quality", "pending", "established"),
            _address("figures", "pending", "established"),
            _address("data_quality", "addressed", "established"),
            _address("figures", "pending", "not_established"),
            resolution=resolution,
        ),
        # The body address differs -- in its response state and in its
        # assessment outcome -- and the comment address does not.
        _item(
            "item-body-first-disagreement",
            _address("data_quality", "addressed", "not_established"),
            _address("sources", "pending", "established"),
            _address("data_quality", "addressed", "not_established"),
            _address("sources", "addressed", "conflicted"),
            resolution=resolution,
        ),
        # The body address differs again, in the same two axes.
        _item(
            "item-body-second-disagreement",
            _address("data_quality", "addressed", "established"),
            _address("sources", "pending", "established"),
            _address("data_quality", "addressed", "established"),
            _address("sources", "addressed", "conflicted"),
            resolution=resolution,
        ),
        # The two read the same, and two of the answers were doubts.
        _item(
            "item-doubt",
            _address(doubt_issue_kind, "pending", "established"),
            _address("sources", doubt_response_state, "established"),
            _address(doubt_issue_kind, "pending", "established"),
            _address("sources", doubt_response_state, "established"),
            resolution=resolution,
        ),
    ]


def _manifest(items: list[dict[str, Any]]) -> dict[str, Any]:
    """A whole manifest, as the JSON file spells it."""
    return {
        "version": "1",
        "corpus": {_FIXTURE: {"project_id": _PROJECT}},
        "partitions": {"train": [_PROJECT]},
        "items": items,
    }


def _report(items: list[dict[str, Any]]) -> Agreement:
    """The agreement of a manifest: read, checked, and computed."""
    return agreement(validate_manifest(_manifest(items)))


def test_the_agreement_names_its_denominator() -> None:
    """A6: the agreement is computed, and its denominator is named.

    **The denominator is part of the answer.** A rate of 0.29 is a
    different claim over seven items than over seven hundred, and a report
    that carries the fraction without the count leaves the reader to guess
    which claim is being made.

    **And the name says what was counted.** The count here is computed from
    the manifest -- the items that carry two readings -- and not read off
    the report, so the assertion is against the data and not against the
    report comparing itself. The words in the name are what separate this
    denominator from the other two candidates: it counts the items **both**
    annotators labelled, not the items in the manifest and not the items
    either annotator labelled.
    """
    items = _corpus_items()
    manifest = validate_manifest(_manifest(items))
    report = agreement(manifest)

    both_labelled = sum(1 for item in manifest.items if len(item.annotations) == 2)
    assert both_labelled == _ITEMS, (
        f"the fixture holds {len(manifest.items)} items and {both_labelled} of them "
        "carry a reading from both annotators. The witness below is about the "
        "report's denominator, and it needs a fixture where the two counts are "
        "computed independently."
    )
    assert report.denominator == both_labelled, (
        f"the agreement is computed over {report.denominator} items, and "
        f"{both_labelled} items carry a reading from both annotators. The "
        "denominator has to be the items both annotators labelled."
    )

    meaning = report.denominator_meaning
    for word, why in (
        ("both", "the items both annotators labelled, not the items either one labelled"),
        ("item", "the denominator counts items, and a name that does not say so does not"),
        (
            "annotator",
            "the denominator counts readings, and a name that does not say so does not",
        ),
        (
            "label",
            "the denominator counts what was labelled, and a name that does not say so does not",
        ),
    ):
        assert word in meaning, (
            f"the denominator's name does not say {word!r}: {meaning!r}. It has to say {why}."
        )

    for view, entry in report.per_view.items():
        assert entry.denominator == report.denominator, (
            f"the view {view!r} is computed over {entry.denominator} items and the "
            f"report over {report.denominator}. One denominator, six views: a "
            "reader comparing two views has to be comparing the same items."
        )


def test_the_agreement_is_computed_from_the_manifest_and_not_entered_by_hand() -> None:
    """The numbers follow the manifest, in the direction the change predicts.

    **One label changes, and three numbers move by exactly one.** The
    comparison is computed over the same seven items in both manifests, so
    the denominator cannot move -- what moves is how many items the two
    annotators read identically, and how many they read alike on the one
    view that changed. **The views that did not change do not move**, which
    is what separates a computed number from a number that was written down
    once and carried forward.
    """
    before = _report(_corpus_items())
    after = _report(_corpus_items(item_two_issue_kind="data_quality"))

    assert before.denominator == after.denominator == _ITEMS, (
        "the denominator moved although no item was added or removed. It counts "
        "the items both annotators labelled, and that count did not change."
    )
    assert before.fully_agreed == 2, (
        f"the corpus reads identically on {before.fully_agreed} items and two of "
        "them do: the item both annotators read the same, and the item both "
        "answered unknown."
    )
    assert after.fully_agreed == 3, (
        f"after one label changes, {after.fully_agreed} items read identically "
        "and three of them do: the second item now reads the same as well."
    )
    assert before.rate == pytest.approx(2 / 7)
    assert after.rate == pytest.approx(3 / 7)

    assert before.per_view["comment_address.issue_kind"].agreed == 5
    assert after.per_view["comment_address.issue_kind"].agreed == 6, (
        "the one view whose label changed did not move by one. A number that "
        "does not follow the manifest was written down."
    )
    for view in (
        "comment_address.response_state",
        "comment_address.assessment_outcome",
        "body_address.issue_kind",
        "body_address.response_state",
        "body_address.assessment_outcome",
    ):
        assert before.per_view[view].agreed == after.per_view[view].agreed, (
            f"the view {view!r} moved although its labels did not change. A "
            "report that counts a change on one view as a change on every view "
            "is not counting anything."
        )


def test_an_empty_denominator_is_no_rate_and_not_zero() -> None:
    """A rate over nothing is ``None``, and zero is kept for a real disagreement.

    **Zero and ``None`` are two different facts.** Zero says "they disagreed
    about every item"; ``None`` says "there was nothing to compare". A
    report that answered zero where the truth is "nothing to compare" would
    be claiming a catastrophe that did not happen, and the reader of the
    number would have no way to tell.
    """
    nothing_compared = LabelAgreement(view="comment_address.issue_kind", agreed=0, denominator=0)
    assert nothing_compared.rate is None, (
        f"the rate over an empty denominator is {nothing_compared.rate!r}, and it "
        "has to be None. Zero would say the two annotators disagreed about "
        "everything, which is a different claim."
    )

    disagreed_about_everything = LabelAgreement(
        view="comment_address.issue_kind", agreed=0, denominator=3
    )
    assert disagreed_about_everything.rate == 0.0, (
        "a real disagreement over three items has a rate of zero, and it has to "
        "keep it: that is the claim zero is meant to make, and it must not be "
        "taken over by the None of an empty denominator."
    )
    assert disagreed_about_everything.rate is not None

    per_view: Mapping[str, LabelAgreement] = {}
    distribution: Mapping[str, Mapping[str, int]] = {}
    empty_report = Agreement(
        denominator=0,
        denominator_meaning="the number of items both annotators labelled",
        fully_agreed=0,
        per_view=per_view,
        distribution=distribution,
    )
    assert empty_report.rate is None, (
        f"the overall rate over an empty denominator is {empty_report.rate!r}, and "
        "it has to be None for the same reason the per-view rate is."
    )


def test_a_manifest_with_no_items_is_refused_rather_than_reported_as_zero() -> None:
    """An empty manifest is refused, and the refusal says why.

    **Refusing is the honest answer here.** The alternative is a report
    whose denominator is zero, and the module's own reason for refusing
    says what zero would claim: that the annotators disagreed about
    everything.
    """
    with pytest.raises(ValueError) as refusal:
        _report([])

    message = str(refusal.value)
    assert "no item" in message, (
        f"the refusal does not say the manifest holds no item: {message!r}. A "
        "refusal that does not say what is wrong leaves the reader to guess."
    )
    assert "zero" in message, (
        f"the refusal does not say why the number is not zero: {message!r}. The "
        "whole difference between refusing and reporting zero is that zero "
        "would be a claim."
    )


def test_unknown_is_in_the_distribution_and_not_filtered_out() -> None:
    """``UNKNOWN`` is counted in the distribution, and the counts add up.

    **Two honest doubts, in two different views.** The corpus carries an
    item both annotators answered ``unknown`` on, once on the comment
    address's issue kind and once on the body address's response state.
    Both are answers, and the distribution has to show them -- a
    distribution that drops the honest ones reports more agreement than the
    two readers had.

    **And every view counts every reading.** Two readings per item over
    seven items is fourteen readings, and a view whose counts come to
    twelve has dropped two.
    """
    report = _report(_corpus_items())

    issue_counts = report.distribution["comment_address.issue_kind"]
    assert issue_counts.get(UNKNOWN) == 2, (
        f"the comment address's issue kinds are {issue_counts}, and the two "
        "unknown answers are not in them. An answer the annotator chose is "
        "counted, not dropped."
    )
    assert report.distribution["body_address.response_state"].get(UNKNOWN) == 2, (
        "the body address's response states do not count the two unknown answers either."
    )
    assert report.distribution["comment_address.response_state"].get(UNKNOWN, 0) == 0

    assert report.distribution["comment_address.issue_kind"] == {
        "data_quality": 10,
        "figures": 1,
        "method_and_hypothesis": 1,
        UNKNOWN: 2,
    }
    assert report.distribution["body_address.assessment_outcome"] == {
        "established": 7,
        "not_established": 5,
        "conflicted": 2,
    }

    for view, counts in report.distribution.items():
        assert sum(counts.values()) == _READINGS_PER_ITEM * report.denominator, (
            f"the view {view!r} counts {sum(counts.values())} answers over "
            f"{report.denominator} items, and there are two readings per item, so "
            "it counts fourteen. The answers that are missing are the ones that "
            "were filtered out."
        )


def test_a_manifest_that_relabels_the_doubts_gets_a_different_distribution() -> None:
    """Relabelling the doubts moves the distribution, and leaves the agreement.

    **The distribution records what the annotators said.** A manifest that
    calls the same four answers something else has a different distribution
    -- and the same agreement, because the two annotators still read the
    same items the same way. A distribution that did not move with the
    labels would be counting something other than the answers.
    """
    with_doubts = _report(_corpus_items())
    relabelled = _report(
        _corpus_items(
            doubt_issue_kind="other",
            doubt_response_state="not_addressed",
        )
    )

    assert with_doubts.distribution != relabelled.distribution, (
        "the two manifests call the same four answers different names, and the "
        "distributions are the same. The distribution records the answers."
    )
    assert relabelled.distribution["comment_address.issue_kind"].get(UNKNOWN, 0) == 0
    assert relabelled.distribution["comment_address.issue_kind"]["other"] == 2, (
        "the relabelled manifest does not count the two other answers under "
        "'other'. A label outside the doubts is still a label, and it counts."
    )
    assert relabelled.distribution["body_address.response_state"]["not_addressed"] == 2
    assert unknown_share(relabelled, "comment_address.issue_kind") == 0.0
    assert unknown_share(with_doubts, "comment_address.issue_kind") == pytest.approx(2 / 14)

    assert with_doubts.fully_agreed == relabelled.fully_agreed == 2, (
        "the relabelled manifest changed the agreement. It changed four answers "
        "and no reading, so the agreement -- which counts the readings -- has to "
        "be where it was."
    )
    assert dict(with_doubts.per_view) == dict(relabelled.per_view), (
        "the per-view counts moved when the doubts were relabelled. The counts "
        "are about the readings, and relabelling an answer both annotators gave "
        "changes no reading."
    )


def test_the_report_carries_one_number_per_address_and_axis() -> None:
    """Two addresses, three axes, six numbers, each with its own count.

    **A comment has two addresses and an address has three axes.** One
    number per comment would lose the distinction the chain was built to
    keep, so the report carries one number per address and axis, and the
    counts below are the ones the seven-item corpus produces.

    **And the counts differ within each address and between the two**, which
    is what makes them six numbers and not one number written six times. A
    report that read the comment address's labels under the body address's
    names would have to put a number where another number belongs, and the
    corpus says which number belongs where.
    """
    report = _report(_corpus_items())

    assert set(report.per_view) == set(_EXPECTED_VIEWS), (
        f"the report carries {sorted(report.per_view)}, and it has to carry one "
        f"number per address and axis: {sorted(_EXPECTED_VIEWS)}."
    )

    expected_agreed = {
        "comment_address.issue_kind": 5,
        "comment_address.response_state": 6,
        "comment_address.assessment_outcome": 7,
        "body_address.issue_kind": 6,
        "body_address.response_state": 5,
        "body_address.assessment_outcome": 4,
    }
    comment_counts = [
        expected_agreed["comment_address.issue_kind"],
        expected_agreed["comment_address.response_state"],
        expected_agreed["comment_address.assessment_outcome"],
    ]
    body_counts = [
        expected_agreed["body_address.issue_kind"],
        expected_agreed["body_address.response_state"],
        expected_agreed["body_address.assessment_outcome"],
    ]
    assert len(set(comment_counts)) == 3, (
        "the comment address's three counts are not all different, so the "
        "corpus cannot tell one axis's number from another's."
    )
    assert len(set(body_counts)) == 3, (
        "the body address's three counts are not all different, so the corpus "
        "cannot tell one axis's number from another's."
    )
    assert comment_counts != body_counts, (
        "the two addresses' counts are the same, so the corpus cannot tell the "
        "comment address's numbers from the body address's."
    )
    for view, agreed in expected_agreed.items():
        entry = report.per_view[view]
        assert entry.view == view, (
            f"the entry filed under {view!r} calls itself {entry.view!r}. A "
            "report whose numbers cannot be found under their own names is a "
            "report nobody can read."
        )
        assert entry.agreed == agreed, (
            f"the view {view!r} counts {entry.agreed} agreements and the corpus "
            f"has {agreed}. Each axis of each address is counted on its own."
        )
        assert entry.denominator == _ITEMS
        assert entry.rate == pytest.approx(agreed / _ITEMS)


def test_fully_agreed_counts_the_items_the_two_read_identically() -> None:
    """The overall agreement is the items that match on *every* label.

    **Both addresses and all three axes.** The corpus reads identically on
    one item and answers ``unknown`` identically on another, so two items
    match everywhere. Four would mean the comment address alone had been
    compared, and three the body address alone -- both of which are numbers
    the report could carry and neither of which is the agreement.
    """
    report = _report(_corpus_items())

    assert report.fully_agreed == 2, (
        f"the report counts {report.fully_agreed} items the two annotators read "
        "identically, and two of them do: the item both read the same, and the "
        "item both answered unknown. An item that differs on one axis of one "
        "address does not count."
    )
    assert report.fully_agreed <= report.denominator, (
        "the number of items read identically is larger than the number of items read at all."
    )
    assert report.rate == pytest.approx(report.fully_agreed / report.denominator)
    assert report.rate == pytest.approx(2 / 7)


def test_unknown_share_is_a_proportion_and_is_none_for_a_view_that_is_not_there() -> None:
    """The share is a fraction of the answers, and an absent view has none.

    **A share, not a count.** The number that matters is the fraction of
    the readings that were honest doubts, because a view that is mostly
    ``unknown`` says the corpus is hard to read, not that the annotators
    agreed.

    **And ``None`` means there was no such view.** A view that exists and
    holds no doubts at all has a share of zero; a view the report does not
    carry has no share to report.
    """
    report = _report(_corpus_items())

    assert unknown_share(report, "comment_address.issue_kind") == pytest.approx(2 / 14), (
        "the comment address's issue kinds carry two unknowns out of fourteen "
        "readings, and the share has to say so."
    )
    assert unknown_share(report, "body_address.response_state") == pytest.approx(2 / 14)
    assert unknown_share(report, "comment_address.response_state") == 0.0, (
        "a view that exists and holds no doubts has a share of zero, and it has "
        "to keep it: zero is what a view with no doubts is worth, and None is "
        "what a view that is not there is worth."
    )
    assert unknown_share(report, "comment_address.no_such_axis") is None, (
        "a view the report does not carry has no share, and it has to be None rather than zero."
    )


def test_an_item_only_one_annotator_read_is_refused_by_name() -> None:
    """An item with one reading is refused, and the refusal names the item.

    **The refusal has to name the item.** A manifest of a hundred rows is
    not a document anybody checks by eye, and a refusal that says only
    "invalid" leaves the annotator to guess which of the hundred rows is
    short.

    **And the reason it is refused is the denominator.** An item one person
    did not read is not in the denominator, and a denominator that silently
    included it would be a number nobody could read back.
    """
    items = _corpus_items()
    solo = dict(items[0])
    solo["item_id"] = "item-solo"
    solo["annotations"] = [items[0]["annotations"][0]]

    with pytest.raises(ValueError) as refusal:
        _report([solo])

    message = str(refusal.value)
    assert "item-solo" in message, (
        f"the refusal does not name the item that is short: {message!r}. A "
        "refusal that does not name it leaves the reader to find it by hand."
    )
    assert "both" in message, (
        f"the refusal does not say why the item is refused: {message!r}. The "
        "reason is the denominator -- the agreement is computed over the items "
        "both annotators labelled -- and a refusal that does not say so is a "
        "refusal without a rule."
    )


def test_a_moment_with_no_offset_is_refused_by_name() -> None:
    """A moment with no offset is refused, and the refusal names the field.

    **Two annotators in two places write the same clock time and mean two
    different moments.** A moment that names no offset cannot be compared
    with the other reader's, so the manifest refuses it rather than letting
    two readings be ordered by a clock time that means nothing on its own.

    **And the refusal names the field.** An item carries three moments --
    one per annotation and one in the resolution -- and a refusal that said
    only "invalid" would leave the annotator to guess which of the three was
    wrong.
    """
    naive_annotation = dict(_corpus_items()[0])
    naive_annotation["item_id"] = "item-naive-annotation"
    first = dict(naive_annotation["annotations"][0])
    first["annotated_at"] = "2026-10-02T09:00:00"
    naive_annotation["annotations"] = [first, naive_annotation["annotations"][1]]

    with pytest.raises(ValueError) as refusal:
        _report([naive_annotation])

    message = str(refusal.value)
    assert "annotated_at" in message, (
        f"the refusal does not name the field that is wrong: {message!r}. An item "
        "carries three moments, and a refusal that does not say which one leaves "
        "the annotator to guess."
    )
    assert "offset" in message, (
        f"the refusal does not say what is missing: {message!r}. The moment has "
        "to name an offset from UTC, and a refusal that does not say so is a "
        "refusal without a rule."
    )

    naive_resolution = dict(_corpus_items()[0])
    naive_resolution["item_id"] = "item-naive-resolution"
    resolution = dict(naive_resolution["resolution"])
    resolution["resolved_at"] = "2026-10-03T08:00:00"
    naive_resolution["resolution"] = resolution

    with pytest.raises(ValueError) as refusal:
        _report([naive_resolution])

    message = str(refusal.value)
    assert "resolved_at" in message, (
        f"the refusal does not name the field that is wrong: {message!r}. The "
        "arbiter's moment is a different field from the annotators', and the "
        "refusal has to say which one."
    )
    assert "offset" in message, (
        f"the refusal does not say what is missing: {message!r}. The moment has "
        "to name an offset from UTC, and a refusal that does not say so is a "
        "refusal without a rule."
    )


def test_a_moment_with_an_offset_is_accepted_in_either_spelling() -> None:
    """An offset may be written as a number or as a ``Z``, and both are read.

    **The rule is about the offset, not about one spelling of it.** A
    manifest that had to write ``+00:00`` and nothing else would refuse the
    ``Z`` that half the world's tooling writes, and an annotator would be
    turned away by a rule about spelling rather than about time.
    """
    with_offset = _report(_corpus_items())

    as_z = _corpus_items()
    for item in as_z:
        for annotation in item["annotations"]:
            annotation["annotated_at"] = "2026-10-02T09:00:00Z"
    with_z = _report(as_z)

    assert with_z.denominator == with_offset.denominator
    assert with_z.fully_agreed == with_offset.fully_agreed
    assert dict(with_z.per_view) == dict(with_offset.per_view)


def test_the_resolution_does_not_change_the_agreement() -> None:
    """The report is a statement about the two annotators, not about the arbiter.

    **The arbiter's answer is a row of its own.** A resolution that
    replaced both readings would leave nothing to compute an agreement
    over, and the number would be a statement about the arbiter alone. So
    the arbiter's labels may be anything, and the report does not move.
    """
    as_read = _report(_corpus_items())
    with_a_different_arbiter = _report(
        _corpus_items(
            resolution=_resolution(
                _address("other", "not_addressed", "conflicted"),
                _address("other", "not_addressed", "conflicted"),
            )
        )
    )

    assert with_a_different_arbiter.fully_agreed == as_read.fully_agreed
    assert with_a_different_arbiter.denominator == as_read.denominator
    assert dict(with_a_different_arbiter.per_view) == dict(as_read.per_view), (
        "the per-view counts moved when the arbiter's row changed. The "
        "disagreement that was settled is the thing the number is computed "
        "from, and a number computed from the arbiter is a statement about "
        "the arbiter."
    )
    assert dict(with_a_different_arbiter.distribution) == dict(as_read.distribution), (
        "the distribution moved when the arbiter's row changed. The "
        "distribution is what the two annotators said."
    )
