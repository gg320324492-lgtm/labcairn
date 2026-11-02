"""The blind score sheet: anonymous while rated, keyed only after unblinding.

**Why the sheet has two lives.** While a rater works, the sheet must not
say which arm produced what — a rater who knows the arm is rating the
arm's reputation, not its output. So the *blind* sheet is anonymous: every
rated item carries its ratings and nothing that names an arm, and
:func:`load_blind_sheet` **refuses** a document whose items carry an arm
key, because a sheet that arrived with arms visible is a sheet whose
ratings were not blind, whatever the rater promises afterwards.

Unblinding is a separate act with a separate input: :func:`unblind` takes
the anonymous sheet and the mapping from item to arm, and only its output
carries the arm key — ``arm`` is a field an unblinded item has and a blind
item may not.

**The loader refuses, rather than repairs.** A rating that is missing is
not an absent value; a sheet that arrives incomplete is a sheet whose
denominator nobody can state, and the aggregation downstream reports rates
over denominators. So the loader refuses an incomplete sheet instead of
padding it, the same discipline the harness's own counts hold: a rate over
no cases is not zero, and a rate over a sheet whose items nobody counted
is a rate about nothing.

**UNKNOWN is a label.** The protocol is explicit: "the evidence does not
settle this" is a label, not a failure and not a missing value. So
``unknown`` sits beside ``yes`` and ``no`` as a rating value the loader
accepts, and it travels through resolution and aggregation as a first-class
value — never converted to an absence on the way.

**Two raters and an arbiter.** The protocol requires two independent
ratings and an arbiter where they disagree, and the inter-annotator
agreement is reported with its denominator. :func:`resolve_pair` produces
exactly that: one resolved label per item and dimension, carried with
*how* it was reached (agreement or arbitration), and one excluded rating
per item and dimension the two raters disagreed on and no arbiter covers —
excluded, and named, because an agreement rate without the number of items
it was computed over is a number without a meaning.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

#: The five dimensions the protocol measures, per case, each with its own
#: denominator. The keys are the sheet's rating dimensions.
DIMENSIONS: Final[tuple[str, ...]] = (
    "problem_identification",
    "evidence_support",
    "advisor_comprehension",
    "hallucination_mis_citation",
    "abstention",
)

#: The label a rating takes, per dimension. ``unknown`` is a label, not a
#: missing value: the protocol says the evidence not settling a case is a
#: verdict about the case, and it is carried as one.
LABEL_YES: Final = "yes"
LABEL_NO: Final = "no"
LABEL_UNKNOWN: Final = "unknown"
RATING_LABELS: Final[tuple[str, ...]] = (LABEL_YES, LABEL_NO, LABEL_UNKNOWN)

#: The keys whose presence in a blind item means the anonymity is broken.
#:
#: The blind sheet's items carry ratings and nothing that names an arm.
#: A rater who can see the arm is not rating blind, so a document that
#: arrives with any of these keys is refused, not cleaned.
ARM_KEY_VARIANTS: Final[tuple[str, ...]] = (
    "arm",
    "arm_id",
    "arm_key",
    "assigned_arm",
    "deanonymized",
)


@dataclass(frozen=True, slots=True)
class BlindSheetItem:
    """One item as a blind rater saw it: an id and ratings, and no arm."""

    #: The item's id — opaque while blind, keyed to an arm only at
    #: unblinding.
    item_id: str
    #: The rater's label per dimension. Every dimension is present; the
    #: loader refuses a sheet where one is not.
    ratings: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class BlindSheet:
    """One rater's anonymous sheet."""

    #: The sheet's own id, for the record.
    sheet_id: str
    #: Who rated this. A name for the record — the loader does not judge
    #: eligibility; the protocol's rule that a rater took no part in
    #: development is the owner's to satisfy when the rater is chosen.
    rater: str
    #: The items, in the order the document gave them.
    items: tuple[BlindSheetItem, ...]


@dataclass(frozen=True, slots=True)
class UnblindedSheetItem:
    """One item after unblinding: the arm key is now attached."""

    #: The item's id, as the blind sheet carried it.
    item_id: str
    #: The arm that produced this item's output. Present only here — the
    #: blind sheet refuses it.
    arm: str
    #: The rater's label per dimension, unchanged by unblinding.
    ratings: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class UnblindedSheet:
    """One rater's sheet after unblinding."""

    #: The sheet's own id, as the blind sheet carried it.
    sheet_id: str
    #: Who rated this.
    rater: str
    #: The items, now keyed to arms.
    items: tuple[UnblindedSheetItem, ...]


def _ratings_of(document: Mapping[str, Any], item_id: str) -> dict[str, str]:
    """One item's ratings, refused unless every dimension carries a label."""
    raw = document.get("ratings")
    if not isinstance(raw, Mapping):
        msg = f"item {item_id} carries no ratings mapping"
        raise ValueError(msg)
    missing = [dimension for dimension in DIMENSIONS if dimension not in raw]
    if missing:
        msg = (
            f"item {item_id} is missing ratings for "
            f"{', '.join(missing)}; a sheet whose ratings are incomplete "
            "is refused, not padded"
        )
        raise ValueError(msg)
    ratings: dict[str, str] = {}
    for dimension in DIMENSIONS:
        label = str(raw[dimension])
        if label not in RATING_LABELS:
            msg = (
                f"item {item_id} rates {dimension} as {label!r}, which is not "
                f"one of {', '.join(RATING_LABELS)}"
            )
            raise ValueError(msg)
        ratings[dimension] = label
    return ratings


def load_blind_sheet(document: Mapping[str, Any], expected_item_ids: Sequence[str]) -> BlindSheet:
    """Load one rater's anonymous sheet, refusing what must not load.

    The refusals, each one a property a witness holds:

    * the sheet's own fields (``sheet_id``, ``rater``, ``items``) are
      present and the items are not empty;
    * every expected item is present exactly once — a sheet missing an
      item has a denominator nobody can state;
    * every item rates every dimension, with a label the vocabulary
      accepts — ``unknown`` included, because it is a label;
    * **no item carries an arm key.** A blind sheet with a visible arm is
      a sheet that was never blind; the loader refuses it rather than
      stripping the key and rating the result.
    """
    for field in ("sheet_id", "rater", "items"):
        if field not in document:
            msg = f"the sheet carries no {field}"
            raise ValueError(msg)
    items_document = document["items"]
    if not isinstance(items_document, list) or not items_document:
        msg = "the sheet carries no items"
        raise ValueError(msg)
    expected = list(expected_item_ids)
    items: list[BlindSheetItem] = []
    seen: list[str] = []
    for one in items_document:
        if not isinstance(one, Mapping) or "item_id" not in one:
            msg = "an item of the sheet carries no item_id"
            raise ValueError(msg)
        item_id = str(one["item_id"])
        if item_id in seen:
            msg = f"item {item_id} appears twice in the sheet"
            raise ValueError(msg)
        leaked = [key for key in ARM_KEY_VARIANTS if key in one]
        if leaked:
            msg = (
                f"item {item_id} carries the key {leaked[0]!r}, which names an "
                "arm; a blind sheet is anonymous until unblinding, and a "
                "sheet whose ratings arrived with arms visible is refused, "
                "not cleaned"
            )
            raise ValueError(msg)
        items.append(BlindSheetItem(item_id=item_id, ratings=_ratings_of(one, item_id)))
        seen.append(item_id)
    absent = [item_id for item_id in expected if item_id not in seen]
    if absent:
        msg = (
            f"the sheet is missing {len(absent)} of the {len(expected)} expected "
            f"items: {', '.join(absent)}"
        )
        raise ValueError(msg)
    return BlindSheet(
        sheet_id=str(document["sheet_id"]),
        rater=str(document["rater"]),
        items=tuple(items),
    )


def unblind(
    sheet: BlindSheet,
    item_arms: Mapping[str, str],
    valid_arms: Sequence[str],
) -> UnblindedSheet:
    """Attach the arm key to every item, and only now.

    The mapping is the unblinding act itself: item id to arm. It must
    cover every item the sheet rated — an item whose arm is unknown is an
    item the aggregation cannot place, and silently dropping it would move
    the denominator without saying so — and it may name no arm outside the
    run's own five.
    """
    items: list[UnblindedSheetItem] = []
    for item in sheet.items:
        arm = item_arms.get(item.item_id)
        if arm is None:
            msg = (
                f"the unblinding map covers no arm for item {item.item_id}; an "
                "item whose arm is unknown is refused, not dropped"
            )
            raise ValueError(msg)
        if arm not in valid_arms:
            msg = (
                f"item {item.item_id} unblinds to arm {arm!r}, which is not one "
                f"of {', '.join(valid_arms)}"
            )
            raise ValueError(msg)
        items.append(UnblindedSheetItem(item_id=item.item_id, arm=arm, ratings=dict(item.ratings)))
    unknown_items = sorted(set(item_arms) - {item.item_id for item in sheet.items})
    if unknown_items:
        msg = (
            f"the unblinding map names {', '.join(unknown_items)}, which this sheet does not carry"
        )
        raise ValueError(msg)
    return UnblindedSheet(sheet_id=sheet.sheet_id, rater=sheet.rater, items=tuple(items))


@dataclass(frozen=True, slots=True)
class ResolvedRating:
    """One item-and-dimension's settled label, and how it was settled."""

    #: The item the label belongs to.
    item_id: str
    #: The dimension the label rates.
    dimension: str
    #: The settled label.
    label: str
    #: ``agreement`` when the two raters agreed; ``arbitrated`` when the
    #: arbiter settled a disagreement.
    basis: str


@dataclass(frozen=True, slots=True)
class ExcludedRating:
    """One item-and-dimension that no settled label covers, and why.

    Excluded, and named: the aggregation downstream reports its
    denominators, and a case that dropped off without a reason is a
    denominator that moved without anyone seeing it move.
    """

    #: The item that was excluded.
    item_id: str
    #: The dimension that was excluded.
    dimension: str
    #: Why it has no settled label.
    reason: str


def resolve_pair(
    rater_a: BlindSheet,
    rater_b: BlindSheet,
    arbiter: Mapping[tuple[str, str], str],
) -> tuple[tuple[ResolvedRating, ...], tuple[ExcludedRating, ...]]:
    """Settle one label per item and dimension, from two blind sheets.

    The two raters must have rated the same items — the loader already
    guarantees each sheet covers the run's expected items, and this
    function refuses a pair whose item sets differ anyway, because a
    denominator computed over "the items both raters labelled" must not be
    silently different from the one over "the items the run expected".

    For each item and dimension:

    * the raters agree — the label is settled, basis ``agreement``;
    * they disagree and the arbiter names a label for this item and
      dimension — the arbiter's label is settled, basis ``arbitrated``;
    * they disagree and no arbiter resolution covers it — the item and
      dimension is **excluded**, and the exclusion is returned, not
      dropped, so the agreement rate downstream can carry its denominator.
    """
    items_a = {item.item_id: item for item in rater_a.items}
    items_b = {item.item_id: item for item in rater_b.items}
    if set(items_a) != set(items_b):
        msg = (
            "the two raters did not rate the same items; the resolution runs "
            "over the items both raters labelled, and these sheets are not "
            "that"
        )
        raise ValueError(msg)
    resolved: list[ResolvedRating] = []
    excluded: list[ExcludedRating] = []
    for item_id in sorted(items_a):
        one, two = items_a[item_id], items_b[item_id]
        for dimension in DIMENSIONS:
            label_a, label_b = one.ratings[dimension], two.ratings[dimension]
            if label_a == label_b:
                resolved.append(
                    ResolvedRating(
                        item_id=item_id,
                        dimension=dimension,
                        label=label_a,
                        basis="agreement",
                    )
                )
                continue
            arbited = arbiter.get((item_id, dimension))
            if arbited is None:
                excluded.append(
                    ExcludedRating(
                        item_id=item_id,
                        dimension=dimension,
                        reason="the raters disagreed and no arbiter resolution covers it",
                    )
                )
                continue
            if arbited not in RATING_LABELS:
                msg = (
                    f"the arbiter resolves {item_id}/{dimension} as {arbited!r}, "
                    f"which is not one of {', '.join(RATING_LABELS)}"
                )
                raise ValueError(msg)
            resolved.append(
                ResolvedRating(
                    item_id=item_id,
                    dimension=dimension,
                    label=arbited,
                    basis="arbitrated",
                )
            )
    return tuple(resolved), tuple(excluded)
