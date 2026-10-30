"""The manifest's own witness: the refusals, and the split by project.

**What this file watches.** LC-P2-10's T04 put the gold manifest's rules in
one place — :func:`labcairn.papers.gold_manifest.validate_manifest` reads a
manifest and checks it, and :func:`labcairn.papers.gold_manifest.
require_annotated` says whether the gold set is finished. This file is the
witness that those rules are really there.

**Four clauses carry the weight** (LC-P2-10's task breakdown §4):

- **A3** — the two addresses are labelled separately;
- **A4** — every item carries two annotations and an arbiter's resolution;
- **A5** — a disagreement is kept, and the resolution is a row of its own;
- **A7** — the split is by ``PaperProject``, and never by event.

**And a refusal names what it refused.** A manifest is a hundred rows long,
and a refusal that says only "invalid" leaves the annotator to guess which
row to fix. So every refusal below is checked for the *value* it names — the
project, the item, the label, the missing field — and not merely for the fact
that something was raised. A witness that only checked "it raised" would
pass on a message that helps nobody.

**And a moment says where it is.** Two annotators in two places write the
same clock time and mean different moments, so a moment with no offset
cannot be compared with the other reader's moment — and the manifest refuses
one that names none.

**The manifests are built here, not read.** The manifest in the tree belongs
to another task and it changes under the annotators' hands; a witness that
read that file would be a witness of whatever the file happened to say. These
tests construct their own manifests, so they watch the rules and not the
data.
"""

from __future__ import annotations

from typing import Any

import pytest

from labcairn.papers.gold_manifest import (
    ANNOTATORS_PER_ITEM,
    GoldManifest,
    require_annotated,
    validate_manifest,
)
from labcairn.papers.labels import (
    ASSESSMENT_LABELS,
    ISSUE_LABELS,
    RESPONSE_LABELS,
    UNKNOWN,
    AnnotationAxis,
)

pytestmark = pytest.mark.unit

#: The three axes, as the manifest spells them.
_AXES = (
    AnnotationAxis.ISSUE_KIND,
    AnnotationAxis.RESPONSE_STATE,
    AnnotationAxis.ASSESSMENT_OUTCOME,
)

#: Issue kinds used by the manifests below, all of them in the closed set.
_ISSUE_METHOD = "method_and_hypothesis"
_ISSUE_LANGUAGE = "language_and_format"
_ISSUE_DATA = "data_quality"

#: The other two axes' answers, in their closed sets.
_RESPONSE = "addressed"
_ASSESSMENT = "established"


def _address(
    issue_kind: str,
    response_state: str = _RESPONSE,
    assessment_outcome: str = _ASSESSMENT,
) -> dict[str, str]:
    """One address's three labels, as the manifest spells them."""
    return {
        AnnotationAxis.ISSUE_KIND: issue_kind,
        AnnotationAxis.RESPONSE_STATE: response_state,
        AnnotationAxis.ASSESSMENT_OUTCOME: assessment_outcome,
    }


def _annotation(
    annotator_id: str,
    comment_issue: str = _ISSUE_METHOD,
    body_issue: str = _ISSUE_LANGUAGE,
    *,
    annotated_at: str = "2026-03-01T09:00:00+00:00",
) -> dict[str, Any]:
    """One annotator's reading of one item, with both addresses labelled."""
    return {
        "annotator_id": annotator_id,
        "annotated_at": annotated_at,
        "comment_address": _address(comment_issue),
        "body_address": _address(body_issue),
    }


def _resolution(
    arbiter_id: str = "arbiter-1",
    comment_issue: str = _ISSUE_METHOD,
    body_issue: str = _ISSUE_LANGUAGE,
    *,
    resolved_at: str = "2026-03-02T12:00:00+00:00",
) -> dict[str, Any]:
    """The arbiter's answer, as a row of its own."""
    return {
        "arbiter_id": arbiter_id,
        "resolved_at": resolved_at,
        "comment_address": _address(comment_issue),
        "body_address": _address(body_issue),
    }


def _readings(
    first: str = _ISSUE_METHOD,
    second: str = _ISSUE_METHOD,
    *,
    annotators: tuple[str, str] = ("ann-1", "ann-2"),
) -> list[dict[str, Any]]:
    """Two readings by two different annotators.

    The two default to the same labels, which is what two people who agree
    look like; the callers that want a disagreement pass different ones.
    """
    return [
        _annotation(annotators[0], first),
        _annotation(annotators[1], second),
    ]


def _item(
    item_id: str,
    project_id: str,
    version_id: str = "v1",
    *,
    annotations: list[dict[str, Any]] | None = None,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One item of a manifest.

    **Two defaults that mean different things.** ``annotations=None`` is the
    standard pair of independent readings; ``resolution=None`` is an item with
    **no** resolution at all — the key is left out, because "the arbiter has
    not answered this one" is what an unfinished gold set looks like.
    """
    readings = _readings() if annotations is None else annotations
    item: dict[str, Any] = {
        "item_id": item_id,
        "project_id": project_id,
        "version_id": version_id,
        "feedback_id": f"fb-{item_id}",
        "fixture": "fixture-alpha",
        "comment_id": f"comment-{item_id}",
        "annotations": readings,
    }
    if resolution is not None:
        item["resolution"] = resolution
    return item


def _manifest(
    items: list[dict[str, Any]],
    *,
    partitions: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """A whole manifest, ready to be read.

    The default split carries two projects, one per partition, so that an item
    naming a project the split does not carry is refused rather than quietly
    accepted.
    """
    return {
        "version": "1",
        "corpus": {"corpus-1": {"fixture": "fixture-alpha"}},
        "partitions": ({"train": ["p-1"], "test": ["p-2"]} if partitions is None else partitions),
        "items": items,
    }


def _read_manifest(
    items: list[dict[str, Any]],
    *,
    partitions: dict[str, list[str]] | None = None,
) -> GoldManifest:
    """The manifest, read and checked."""
    return validate_manifest(_manifest(items, partitions=partitions))


def test_both_addresses_are_labelled() -> None:
    """A3: the two addresses are labelled separately, and both are kept.

    **A comment has two addresses** — the comment element in the comments
    part, and the body-side paragraph and offsets — and an annotation that
    labels only one of them loses the distinction the chain was built to
    keep. So the two are separate fields, each with its own three labels, and
    **the two may disagree**: an annotator can point at a method in the
    comment and a formatting problem in the body.

    **And the manifest keeps both.** A reader that stored one address twice
    would look right on every item where the two agree, and wrong on every
    item where they do not — so the witness uses an item where they do not.
    """
    readings = [
        _annotation("ann-1", _ISSUE_METHOD, _ISSUE_LANGUAGE),
        _annotation("ann-2", _ISSUE_METHOD, _ISSUE_LANGUAGE),
    ]
    manifest = _read_manifest([_item("item-a", "p-1", annotations=readings)])

    item = manifest.item("item-a")
    assert item is not None, "the manifest lost the item it was given."

    for position, annotation in enumerate(item.annotations):
        assert annotation.comment_address.issue_kind == _ISSUE_METHOD, (
            f"reading {position} lost the comment address's label: "
            f"{annotation.comment_address.as_mapping()!r}. A comment's own "
            "element is one of its two addresses."
        )
        assert annotation.body_address.issue_kind == _ISSUE_LANGUAGE, (
            f"reading {position} lost the body address's label: "
            f"{annotation.body_address.as_mapping()!r}. The body-side paragraph "
            "and offsets are the other address, and they carry their own answer."
        )

    for position, annotation in enumerate(item.annotations):
        for address_name, address in (
            ("comment_address", annotation.comment_address),
            ("body_address", annotation.body_address),
        ):
            assert set(address.as_mapping()) == set(_AXES), (
                f"reading {position}'s {address_name} does not carry the three "
                f"axes: {sorted(address.as_mapping())!r}. An address that "
                "answers one question is not an address."
            )
            assert address.issue_kind in ISSUE_LABELS, (
                f"reading {position}'s {address_name} carries an issue kind "
                f"outside the closed set: {address.issue_kind!r}."
            )
            assert address.response_state in RESPONSE_LABELS, (
                f"reading {position}'s {address_name} carries a response state "
                f"outside the closed set: {address.response_state!r}."
            )
            assert address.assessment_outcome in ASSESSMENT_LABELS, (
                f"reading {position}'s {address_name} carries an assessment "
                f"outcome outside the closed set: {address.assessment_outcome!r}."
            )

    assert not item.annotations[0].comment_address.agrees_with(item.annotations[0].body_address), (
        "the comment address and the body address hold the same labels, so the "
        "manifest is not keeping the two apart. The witness labelled them "
        "differently on purpose."
    )


def test_every_item_has_two_annotations_and_a_resolution() -> None:
    """A4: every item carries two annotations and an arbiter's resolution.

    **Two things, and the manifest says which is missing.** An item with one
    reading is not an item two people read, and an item with no resolution is
    an item the arbiter has not settled — and a reviewer wants to know how
    much is left, so the refusal names **every** short item rather than
    stopping at the first.
    """
    complete = _read_manifest(
        [
            _item("item-a", "p-1", resolution=_resolution()),
            _item("item-b", "p-2", resolution=_resolution()),
        ]
    )

    for item in complete.items:
        assert len(item.annotations) == ANNOTATORS_PER_ITEM == 2, (
            f"item {item.item_id!r} carries {len(item.annotations)} reading(s). "
            "The manifest requires two independent ones."
        )
        assert item.resolution is not None, (
            f"item {item.item_id!r} carries no resolution. The arbiter's answer "
            "is a row of its own."
        )

    require_annotated(complete)

    unfinished = _read_manifest(
        [
            _item("item-a", "p-1", resolution=_resolution()),
            _item(
                "item-b",
                "p-2",
                annotations=[_annotation("ann-1")],
                resolution=_resolution(),
            ),
            _item("item-c", "p-1", annotations=[_annotation("ann-1")]),
        ]
    )

    with pytest.raises(ValueError) as refusal:
        require_annotated(unfinished)

    message = str(refusal.value)
    assert "item-b" in message, (
        f"the refusal does not name the item with one reading: {message!r}. A "
        "reviewer cannot fix a row the refusal does not point at."
    )
    assert "item-c" in message, (
        f"the refusal does not name the item with no resolution: {message!r}. "
        "Every short item is named, not only the first — a reviewer wants to "
        "know how much is left."
    )
    assert "has no resolution" in message, (
        f"the refusal does not say that a resolution is missing: {message!r}."
    )


def test_a_resolution_does_not_overwrite_the_disagreement() -> None:
    """A5: a disagreement is kept, and the resolution is a row of its own.

    **A disagreement that existed is information** — it is the thing the
    agreement number is computed from. So the arbiter's answer is recorded
    *beside* the two readings, and the two readings keep the labels the
    annotators gave them.

    **The witness is that the disagreement is still computable.** If the
    resolution had been written over the readings, the two annotations would
    carry the arbiter's labels, would agree with each other, and would carry
    the arbiter's identity. Every one of those is checked here, because
    "the resolution is a third row" and "the resolution replaced the rows"
    are told apart by what the two rows still say.
    """
    manifest = _read_manifest(
        [
            _item(
                "item-a",
                "p-1",
                annotations=_readings(_ISSUE_METHOD, _ISSUE_DATA),
                resolution=_resolution("arbiter-1", _ISSUE_LANGUAGE),
            )
        ]
    )

    item = manifest.item("item-a")
    assert item is not None, "the manifest lost the item it was given."

    assert len(item.annotations) == 2, (
        f"the item carries {len(item.annotations)} reading(s) after the "
        "resolution was read. The arbiter's answer is a row of its own, and "
        "the two readings are still there."
    )

    assert item.annotations[0].comment_address.issue_kind == _ISSUE_METHOD, (
        "the first reading no longer carries the label its annotator gave it: "
        f"{item.annotations[0].comment_address.as_mapping()!r}. A resolution "
        "that overwrote a reading would leave the agreement number computed "
        "over the arbiter alone."
    )
    assert item.annotations[1].comment_address.issue_kind == _ISSUE_DATA, (
        "the second reading no longer carries the label its annotator gave it: "
        f"{item.annotations[1].comment_address.as_mapping()!r}."
    )
    assert not item.annotations[0].comment_address.agrees_with(
        item.annotations[1].comment_address
    ), (
        "the two readings agree, so the disagreement is gone. The arbiter's "
        "answer was written over the readings rather than beside them."
    )
    assert [annotation.annotator_id for annotation in item.annotations] == [
        "ann-1",
        "ann-2",
    ], (
        "the readings no longer carry the annotators who made them. A "
        "resolution that replaced them would leave nobody's reading but the "
        "arbiter's in the manifest."
    )

    assert item.resolution is not None, "the item lost its resolution."
    assert not hasattr(item.resolution, "annotator_id"), (
        "the resolution carries an annotator id, so it is shaped like a "
        "reading rather than a row of its own."
    )
    assert item.resolution.arbiter_id == "arbiter-1"
    assert item.resolution.comment_address.issue_kind == _ISSUE_LANGUAGE, (
        "the resolution does not carry the arbiter's own answer: "
        f"{item.resolution.comment_address.as_mapping()!r}."
    )
    assert item.resolution.comment_address.issue_kind not in (
        item.annotations[0].comment_address.issue_kind,
        item.annotations[1].comment_address.issue_kind,
    ), (
        "the resolution carries one of the two readings' labels, so the third "
        "row is not the arbiter's own answer."
    )


def test_the_split_is_by_project_and_never_by_event() -> None:
    """A7: the split is by ``PaperProject``, and never by event.

    **Two versions of one paper are two observations of one thing.** A split
    by row would put version 1 in training and version 2 in test, and a
    system that memorised version 1 would score on version 2 without having
    generalised. So the partition names the *project*, once, and every row of
    that project lands in it.

    **And a project in two partitions is refused by name** — with both
    partitions named, because the reader has to know which two to reconcile.
    """
    manifest = _read_manifest(
        [
            _item("item-v1", "p-1", "v1", resolution=_resolution()),
            _item("item-v2", "p-1", "v2", resolution=_resolution()),
            _item("item-other", "p-2", "v1", resolution=_resolution()),
        ],
        partitions={"train": ["p-1"], "test": ["p-2"]},
    )

    assert manifest.partitions == {"train": ("p-1",), "test": ("p-2",)}, (
        f"the split does not hold projects: {manifest.partitions!r}. Two "
        "versions of one paper are two observations of one thing, so the "
        "partition names the paper and not the row."
    )

    where = {
        project: name for name, projects in manifest.partitions.items() for project in projects
    }
    versions = [item.version_id for item in manifest.items if item.project_id == "p-1"]
    assert sorted(versions) == ["v1", "v2"], (
        f"the two versions of p-1 are not both in the manifest: {versions!r}."
    )
    assert {where[item.project_id] for item in manifest.items if item.project_id == "p-1"} == {
        "train"
    }, (
        "the two versions of p-1 are not in the same partition, so the split "
        "was made by row rather than by project."
    )

    with pytest.raises(ValueError) as refusal:
        _read_manifest(
            [_item("item-a", "p-1", resolution=_resolution())],
            partitions={"train": ["p-1"], "test": ["p-1", "p-2"]},
        )

    message = str(refusal.value)
    assert "p-1" in message, (
        f"the refusal does not name the project that is in two partitions: "
        f"{message!r}. A refusal that does not name it leaves the reader to "
        "guess which project to move."
    )
    assert "train" in message and "test" in message, (
        f"the refusal does not name both partitions: {message!r}. The reader "
        "has to know which two to reconcile."
    )


def test_the_manifest_refuses_a_label_outside_the_set_by_name() -> None:
    """A label outside T00's set is refused, wherever it is written.

    **In all three places a label can appear** — a reading's comment address,
    a reading's body address, and the arbiter's resolution — because a
    vocabulary that is closed on the annotations and open on the resolution
    is not closed at all.

    **And the refusal names the word that was wrong.** A manifest is a
    hundred rows; a refusal that says only "invalid" leaves the annotator to
    guess which of three words it was.
    """
    bad_reading = _annotation("ann-1", "edit_intent")
    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[bad_reading])])

    message = str(refusal.value)
    assert "edit_intent" in message, (
        f"the refusal does not name the label that was wrong: {message!r}. A "
        "refusal that does not name it leaves the person who wrote it to guess."
    )

    bad_body = _annotation("ann-1", _ISSUE_METHOD, "edit_intent")
    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[bad_body])])

    assert "edit_intent" in str(refusal.value), (
        f"a label outside the set on the body address is not named: "
        f"{str(refusal.value)!r}. The set is closed on both addresses."
    )

    with pytest.raises(ValueError) as refusal:
        _read_manifest(
            [
                _item(
                    "item-a",
                    "p-1",
                    annotations=_readings(),
                    resolution=_resolution("arbiter-1", "edit_intent"),
                )
            ]
        )

    assert "edit_intent" in str(refusal.value), (
        f"a label outside the set on the resolution is not named: "
        f"{str(refusal.value)!r}. The arbiter chooses from the same set as the "
        "annotators."
    )


def test_the_label_refusal_names_the_axis_and_its_accepted_labels() -> None:
    """The refusal comes from the label set, and it says which axis and which labels.

    **The three axes have different vocabularies**, so a refusal that listed
    the wrong axis's labels would be worse than no list at all — the reader
    would be offered words that do not answer the question they asked.

    **And the list is the accepted set, in full**, which is what makes the
    refusal fixable: the person who wrote the row can see the words they
    could have written.
    """
    wrong_axis = _annotation("ann-1")
    wrong_axis["comment_address"] = _address(_ISSUE_METHOD, "data_quality")

    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[wrong_axis])])

    message = str(refusal.value)
    assert "data_quality" in message, (
        f"the refusal does not name the label that was wrong: {message!r}."
    )
    assert AnnotationAxis.RESPONSE_STATE in message, (
        f"the refusal does not name the axis the label was written on: "
        f"{message!r}. A label is an answer to an axis, and a refusal that "
        "does not say which one leaves the same guess open."
    )
    for accepted in sorted(RESPONSE_LABELS):
        assert accepted in message, (
            f"the refusal does not list {accepted!r}, so the accepted labels "
            f"are not all in it: {message!r}. A closed set that cannot be read "
            "cannot be used to fix a label."
        )

    unknown_is_an_answer = _annotation("ann-1")
    unknown_is_an_answer["comment_address"] = _address(_ISSUE_METHOD, UNKNOWN)
    manifest = _read_manifest([_item("item-a", "p-1", annotations=[unknown_is_an_answer])])
    item = manifest.item("item-a")
    assert item is not None
    assert item.annotations[0].comment_address.response_state == UNKNOWN, (
        "the manifest does not carry 'unknown' as an answer. It is in the "
        "closed set, and it is scored as an answer rather than as a hole."
    )


def test_the_manifest_refuses_an_annotation_with_no_annotator() -> None:
    """An annotation with no annotator id is refused, and the field is named.

    **An annotation without an annotator is a reading nobody made.** And a
    reader that guessed the missing one would be reading a different
    manifest, so the refusal names the field that is absent.
    """
    reading = _annotation("ann-1")
    del reading["annotator_id"]

    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[reading])])

    message = str(refusal.value)
    assert "annotator_id" in message, (
        f"the refusal does not name the missing field: {message!r}. A reader "
        "that guesses which field was absent is reading a different manifest."
    )
    assert "item-a" in message, f"the refusal does not name the item it refused: {message!r}."

    blank = _annotation("ann-1")
    blank["annotator_id"] = "   "
    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[blank])])

    assert "annotator_id" in str(refusal.value), (
        f"an annotator id that is blank is not refused by name: "
        f"{str(refusal.value)!r}. An id that is empty is not one."
    )


def test_the_manifest_refuses_an_annotation_with_no_moment() -> None:
    """An annotation with no moment is refused, and the field is named.

    **A reading with no moment cannot be ordered against the other reading**,
    so the moment is required — and a moment that does not parse is not a
    moment.
    """
    reading = _annotation("ann-1")
    del reading["annotated_at"]

    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[reading])])

    message = str(refusal.value)
    assert "annotated_at" in message, (
        f"the refusal does not name the missing field: {message!r}. A reading "
        "with no moment cannot be ordered against the other reading."
    )
    assert "item-a" in message, f"the refusal does not name the item it refused: {message!r}."

    unparseable = _annotation("ann-1", annotated_at="the other day")
    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[unparseable])])

    assert "annotated_at" in str(refusal.value), (
        f"a moment that does not parse is not refused by name: {str(refusal.value)!r}."
    )


def test_the_manifest_refuses_a_moment_with_no_offset() -> None:
    """A moment that names no offset is refused, and the field is named.

    **Two annotators in two places write the same clock time and mean
    different moments.** A moment with no offset cannot be compared with the
    other reader's moment, so the string has to carry one — an offset, or a
    ``Z`` for UTC.

    **And the refusal names the field**, because the two moments in a
    manifest are named differently: the reader's is ``annotated_at`` and the
    arbiter's is ``resolved_at``, and only one of them can be the wrong one.
    """
    naive_reading = _annotation("ann-1", annotated_at="2026-03-01T09:00:00")
    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=[naive_reading])])

    message = str(refusal.value)
    assert "annotated_at" in message, (
        f"the refusal does not name the field: {message!r}. A reader that "
        "guesses which moment was wrong is reading a different manifest."
    )
    assert "offset" in message, (
        f"the refusal does not say that an offset is needed: {message!r}. The "
        "annotator has to know what to change."
    )
    assert "2026-03-01T09:00:00" in message, (
        f"the refusal does not quote the moment it refused: {message!r}."
    )
    assert "item-a" in message, f"the refusal does not name the item it refused: {message!r}."

    naive_resolution = _resolution("arbiter-1")
    naive_resolution["resolved_at"] = "2026-03-02T12:00:00"
    with pytest.raises(ValueError) as refusal:
        _read_manifest(
            [
                _item(
                    "item-a",
                    "p-1",
                    annotations=_readings(),
                    resolution=naive_resolution,
                )
            ]
        )

    message = str(refusal.value)
    assert "resolved_at" in message, (
        f"the refusal does not name the field: {message!r}. The arbiter's "
        "moment is named differently from the readers'."
    )
    assert "offset" in message, f"the refusal does not say that an offset is needed: {message!r}."


def test_the_manifest_refuses_two_annotations_by_one_annotator() -> None:
    """Two readings by one annotator are refused: the readings must be independent.

    **One person reading twice is one reading**, and an agreement number
    computed over it would be a statement about that annotator's consistency
    on a single reading rather than about two readers at all.
    """
    readings = _readings(annotators=("ann-1", "ann-1"))

    with pytest.raises(ValueError) as refusal:
        _read_manifest([_item("item-a", "p-1", annotations=readings)])

    message = str(refusal.value)
    assert "ann-1" in message, (
        f"the refusal does not name the annotator who read twice: {message!r}."
    )
    assert "item-a" in message, f"the refusal does not name the item it refused: {message!r}."


def test_the_manifest_refuses_an_arbiter_who_is_one_of_the_annotators() -> None:
    """An arbiter who is one of the two annotators is refused.

    **The arbiter is the third reader.** An arbiter who is one of the two
    annotators has not arbitrated anything — they have read the item a
    second time and written their own answer over the top. The agreement
    number over that item would then be a statement about one reader
    rather than about two, and the disagreement the arbiter was asked to
    settle would have been settled by a party to it.

    **This is a rule of the manifest's own**, and not of the annotator's
    discipline: the manifest is read by three parties, and a manifest
    that admits this reading would be read differently by each of them.
    """
    readings = _readings(annotators=("ann-1", "ann-2"))

    with pytest.raises(ValueError) as refusal:
        _read_manifest(
            [
                _item(
                    "item-a",
                    "p-1",
                    annotations=readings,
                    resolution=_resolution("ann-1"),
                )
            ]
        )

    message = str(refusal.value)
    assert "ann-1" in message, (
        f"the refusal does not name the arbiter who is one of the annotators: {message!r}."
    )
    assert "item-a" in message, f"the refusal does not name the item it refused: {message!r}."

    # **And the refusal is about the arbiter, not about the annotator.** A
    # manifest whose arbiter is a third reader is accepted, so the refusal
    # above is about the identity and not about resolutions being present.
    accepted = _read_manifest(
        [
            _item(
                "item-a",
                "p-1",
                annotations=readings,
                resolution=_resolution("ann-3"),
            )
        ]
    )
    assert accepted.items[0].resolution is not None, (
        "the manifest refused a resolution whose arbiter is a third reader. The "
        "rule is about the arbiter's identity and not about resolutions."
    )


def test_the_manifest_refuses_a_repeated_item_id() -> None:
    """An item id used twice is refused, and the id is named.

    **An id is minted once**, and a second row wearing one name would be
    counted twice — once in the agreement's denominator and once in the
    distribution.
    """
    with pytest.raises(ValueError) as refusal:
        _read_manifest(
            [
                _item("item-a", "p-1", resolution=_resolution()),
                _item("item-a", "p-2", resolution=_resolution()),
            ]
        )

    message = str(refusal.value)
    assert "item-a" in message, (
        f"the refusal does not name the id that was used twice: {message!r}."
    )


def test_the_manifest_refuses_an_item_whose_project_is_in_no_partition() -> None:
    """An item whose project is in no partition is refused, and it is named.

    **The split is by project**, so an item outside every partition is an
    item nobody can train on and nobody can test on. The refusal names both
    the item and the project, because the project is what has to be put
    somewhere.
    """
    with pytest.raises(ValueError) as refusal:
        _read_manifest(
            [_item("item-a", "p-9", resolution=_resolution())],
            partitions={"train": ["p-1"]},
        )

    message = str(refusal.value)
    assert "p-9" in message, (
        f"the refusal does not name the project that is in no partition: "
        f"{message!r}. The project is what has to be put somewhere."
    )
    assert "item-a" in message, f"the refusal does not name the item it refused: {message!r}."
