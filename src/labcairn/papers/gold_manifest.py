"""The gold manifest: what a person annotated, and what it was read against.

**What this module is.** LC-P2-10's manifest, as data. One entry per
comment in the corpus, carrying **the two addresses** the chain gives a
comment, **the two independent annotations**, and **the arbiter's
resolution** — and it is read by three different parties: the agreement
computation (T03), the manifest's own witness (T04), and LC-P2-11, which
will read this gold set to derive its guidance rules.

**Why the manifest is parsed here and not in each reader.** A rule that
lives in a test is a rule that only that test enforces, and a rule that is
typed twice is a rule the two spellings will disagree about. **The checks
below are the manifest's**, and every reader gets them by calling the same
function — so a manifest that is well-formed for one reader is well-formed
for all of them.

**And the checks refuse by name.** A manifest that names a label outside
the closed set is refused with the label in the message; a manifest whose
project sits in two partitions is refused with the project in the message.
A refusal that says only "invalid" leaves the annotator or the reviewer to
guess which of the hundred rows was wrong.

**The resolution is a row of its own, and never an overwrite.** A
disagreement that existed is information — it is the thing the agreement
number is computed from — so the arbiter's answer is recorded beside the
two annotations rather than on top of them. A resolution that replaced
both would leave nothing to compute an agreement over, and the number
would be a statement about the arbiter alone.

**And the arbiter is the third reader.** The arbiter is somebody other
than the two annotators: an arbiter who is one of the two has not
arbitrated anything, they have read the item twice, and the agreement
number over that item would be a statement about one reader. So the
arbiter's id is refused when it names one of the item's own annotators.

**The split is by ``PaperProject``, never by event.** Two versions of one
paper are two observations of one thing, and a split by row would put
version 1 in one partition and version 2 in the other — where a system that
memorised version 1 would score on version 2 without having generalised.
So every row of one project is in the same partition, and
:func:`validate_manifest` says so when it is not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from labcairn.papers.labels import (
    ASSESSMENT_LABELS,
    ISSUE_LABELS,
    RESPONSE_LABELS,
    UNKNOWN,
    AnnotationAxis,
    check_label,
)

#: Where the manifest lives in the tree.
MANIFEST_RELATIVE_PATH: Final[Path] = Path("docs") / "papers" / "gold-set-manifest.json"

#: The labels each axis accepts, keyed by axis.
_AXIS_LABELS: Final[Mapping[str, frozenset[str]]] = {
    AnnotationAxis.ISSUE_KIND: ISSUE_LABELS,
    AnnotationAxis.RESPONSE_STATE: RESPONSE_LABELS,
    AnnotationAxis.ASSESSMENT_OUTCOME: ASSESSMENT_LABELS,
}

#: The two addresses a comment has. **Two, and not one.**
#:
#: The comment element in the comments part is *what was written*; the
#: body-side paragraph and offsets are *where it was written about*. A
#: comment that keeps only one answers only one of them, and an annotation
#: that labels only one loses the distinction the chain was built to keep.
ADDRESSES: Final[tuple[str, str]] = ("comment_address", "body_address")

#: How many independent annotations every item carries.
#:
#: **Two, and the two must be different people.** One annotator twice is
#: one annotator, and the agreement number computed over it would be a
#: statement about the annotator's consistency on a single reading.
ANNOTATORS_PER_ITEM: Final[int] = 2


@dataclass(frozen=True, slots=True)
class AddressLabels:
    """One address's labels: the three axes, each with one answer."""

    issue_kind: str
    response_state: str
    assessment_outcome: str

    def as_mapping(self) -> Mapping[str, str]:
        """The labels as the manifest spells them."""
        return {
            AnnotationAxis.ISSUE_KIND: self.issue_kind,
            AnnotationAxis.RESPONSE_STATE: self.response_state,
            AnnotationAxis.ASSESSMENT_OUTCOME: self.assessment_outcome,
        }

    def agrees_with(self, other: AddressLabels) -> bool:
        """Whether the two readings are the same, on all three axes."""
        return self.as_mapping() == other.as_mapping()


@dataclass(frozen=True, slots=True)
class Annotation:
    """One annotator's reading of one item.

    **Who, and when.** An annotation without an annotator is a reading
    nobody made, and one without a moment cannot be ordered against the
    other reading — so both are required, and the manifest's witness says so.
    """

    annotator_id: str
    annotated_at: datetime
    comment_address: AddressLabels
    body_address: AddressLabels


@dataclass(frozen=True, slots=True)
class Resolution:
    """The arbiter's answer, as a row of its own.

    **Beside the two annotations, never over them.** See the module
    docstring: the disagreement is the thing the agreement number is
    computed from.
    """

    arbiter_id: str
    resolved_at: datetime
    comment_address: AddressLabels
    body_address: AddressLabels


@dataclass(frozen=True, slots=True)
class GoldItem:
    """One comment in the corpus, with everything said about it.

    **The two addresses are fields, not a convention.** The comment's own
    locator and the body's paragraph and offsets are separate, because
    LC-P2-09's first clause is that a comment has two.
    """

    item_id: str
    project_id: str
    version_id: str
    feedback_id: str
    #: The fixture in the synthetic corpus this item reads.
    fixture: str
    #: The comment inside that fixture.
    comment_id: str
    #: The comment element's address, as the chain spells a locator.
    comment_locator: Mapping[str, Any] | None
    #: The body-side address: which paragraph, and which characters of it.
    paragraph: int | None
    start: int | None
    end: int | None
    #: The two independent readings.
    annotations: tuple[Annotation, ...]
    #: The arbiter's answer.
    resolution: Resolution | None


@dataclass(frozen=True, slots=True)
class GoldManifest:
    """The whole manifest: the corpus it reads, the split, and the items."""

    version: str
    #: The corpus the items read, and the fixture each project came from.
    corpus: Mapping[str, Mapping[str, Any]]
    #: The split: partition name to the projects in it.
    partitions: Mapping[str, tuple[str, ...]]
    items: tuple[GoldItem, ...]

    def item(self, item_id: str) -> GoldItem | None:
        """The item with that id, or ``None`` when there is none."""
        for candidate in self.items:
            if candidate.item_id == item_id:
                return candidate
        return None


@dataclass(frozen=True, slots=True)
class LabelAgreement:
    """How often two annotators gave the same answer on one axis."""

    #: The axis, spelled as ``address.axis`` — e.g. ``comment_address.issue_kind``.
    view: str
    #: How many items the two annotators agreed on.
    agreed: int
    #: How many items the number is computed over.
    denominator: int

    @property
    def rate(self) -> float | None:
        """The agreement as a fraction, or ``None`` when nothing was compared.

        **``None`` and not zero.** Zero says "they disagreed on every item";
        ``None`` says "there was nothing to compare", and those are
        different facts.
        """
        if self.denominator == 0:
            return None
        return self.agreed / self.denominator


@dataclass(frozen=True, slots=True)
class Agreement:
    """The agreement between the two annotators, and the denominator it used.

    **The denominator is part of the answer.** It is the number of items
    **both** annotators labelled — not the number of items in the manifest,
    and not the number either annotator labelled. A number without its
    denominator is a number nobody can read, so this carries it, and
    :attr:`denominator_meaning` says in words what it counted.
    """

    #: How many items the agreement is computed over.
    denominator: int
    #: The denominator, in words.
    denominator_meaning: str
    #: How many of those items the two annotators read identically, on
    #: every axis of both addresses.
    fully_agreed: int
    #: The agreement on each axis of each address.
    per_view: Mapping[str, LabelAgreement]
    #: How often each label was used, over the two annotations.
    distribution: Mapping[str, Mapping[str, int]]

    @property
    def rate(self) -> float | None:
        """The overall agreement as a fraction, or ``None`` when nothing was compared."""
        if self.denominator == 0:
            return None
        return self.fully_agreed / self.denominator


def _require(mapping: Mapping[str, Any], key: str, where: str) -> Any:
    """The value at *key*, or a refusal that names it.

    :raises ValueError: when the key is absent. **The message names the key
        and where it was expected**, so a reader of the manifest knows which
        row to fix.
    """
    if key not in mapping:
        raise ValueError(
            f"{where} has no {key!r}. A manifest that omits a field is a "
            "manifest that cannot be read, and a reader that guesses the "
            "missing one is reading a different manifest."
        )
    return mapping[key]


def _record(value: Any, where: str) -> Mapping[str, Any]:
    """The nested record at *value*, or a refusal that names it.

    **A nested field is a record, not a word.** A manifest whose
    ``comment_address`` is the number 5 is a manifest this reader cannot
    read, and it has to say so **rather than fall over** — a reader that
    raises a ``TypeError`` deep inside a lookup tells the annotator
    nothing, and a reader that guesses tells them something false.

    :raises ValueError: when the value is not a mapping of fields.
    """
    if not isinstance(value, Mapping):
        raise ValueError(
            f"{where} is {value!r}, and a record is a mapping of its fields. "
            "The manifest says what is in it, and a field that is not a "
            "record cannot be read."
        )
    return value


def _text(mapping: Mapping[str, Any], key: str, where: str) -> str:
    """A non-empty text value at *key*.

    :raises ValueError: when the value is absent or empty.
    """
    value = _require(mapping, key, where)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{where} has no usable {key!r}: {value!r}. An id or a moment that "
            "is empty is not one, and a reading nobody made is not a reading."
        )
    return value


def _moment(mapping: Mapping[str, Any], key: str, where: str) -> datetime:
    """An ISO-8601 moment at *key*.

    :raises ValueError: when the value is absent, is not a moment, or names
        no offset from UTC.
    """
    raw = _require(mapping, key, where)
    if not isinstance(raw, str):
        raise ValueError(
            f"{where} has no usable {key!r}: {raw!r}. The moment is written as an "
            "ISO-8601 string, and a moment nobody can place in time is not one."
        )
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(
            f"{where} has no usable {key!r}: {raw!r}. The moment is written as an "
            "ISO-8601 string, and this one does not parse as one."
        ) from None
    if parsed.tzinfo is None:
        raise ValueError(
            f"{where} has no usable {key!r}: {raw!r}. The moment names no offset "
            "from UTC, and a moment with no offset cannot be compared with the "
            "other reader's moment: two annotators in two places write the "
            "same clock time and mean different moments. The string carries an "
            "offset -- '2026-03-01T09:00:00+00:00', or a 'Z' for UTC."
        )
    return parsed


def _address_labels(mapping: Mapping[str, Any], where: str) -> AddressLabels:
    """One address's three labels, each checked against the closed set.

    :raises ValueError: when a label is outside its axis's set. **The
        refusal names the label**, because a manifest of a hundred rows is
        not a document anybody checks by eye.
    """
    values: dict[str, str] = {}
    for axis in _AXIS_LABELS:
        raw = _require(mapping, axis, where)
        if not isinstance(raw, str):
            raise ValueError(
                f"{where} has no usable {axis!r}: {raw!r}. A label is a word, and "
                "a word that is not there cannot be read."
            )
        try:
            values[axis] = check_label(axis, raw)
        except ValueError as refusal:
            raise ValueError(f"{where}: {refusal}") from None
    return AddressLabels(
        issue_kind=values[AnnotationAxis.ISSUE_KIND],
        response_state=values[AnnotationAxis.RESPONSE_STATE],
        assessment_outcome=values[AnnotationAxis.ASSESSMENT_OUTCOME],
    )


def _annotation(mapping: Mapping[str, Any], where: str) -> Annotation:
    """One annotator's reading, with both addresses labelled."""
    return Annotation(
        annotator_id=_text(mapping, "annotator_id", where),
        annotated_at=_moment(mapping, "annotated_at", where),
        comment_address=_address_labels(
            _record(_require(mapping, "comment_address", where), f"{where} comment_address"),
            f"{where} comment_address",
        ),
        body_address=_address_labels(
            _record(_require(mapping, "body_address", where), f"{where} body_address"),
            f"{where} body_address",
        ),
    )


def _resolution(mapping: Mapping[str, Any], where: str) -> Resolution:
    """The arbiter's answer, with both addresses labelled."""
    return Resolution(
        arbiter_id=_text(mapping, "arbiter_id", where),
        resolved_at=_moment(mapping, "resolved_at", where),
        comment_address=_address_labels(
            _record(_require(mapping, "comment_address", where), f"{where} comment_address"),
            f"{where} comment_address",
        ),
        body_address=_address_labels(
            _record(_require(mapping, "body_address", where), f"{where} body_address"),
            f"{where} body_address",
        ),
    )


def _item(mapping: Mapping[str, Any], index: int) -> GoldItem:
    """One item, read out of the manifest."""
    where = f"item {index}"
    item_id = _text(mapping, "item_id", where)
    where = f"item {item_id!r}"

    raw_annotations = _require(mapping, "annotations", where)
    if not isinstance(raw_annotations, list):
        raise ValueError(
            f"{where} has no usable 'annotations': {raw_annotations!r}. The "
            "annotations are a list, and a list that is not a list cannot be "
            "read."
        )
    annotations = tuple(
        _annotation(
            _record(entry, f"{where} annotation {position}"), f"{where} annotation {position}"
        )
        for position, entry in enumerate(raw_annotations)
    )
    readers = [annotation.annotator_id for annotation in annotations]
    if len(set(readers)) != len(readers):
        raise ValueError(
            f"{where} carries two annotations by the same annotator ({readers}). "
            "The two readings have to be independent, and one person reading "
            "twice is one reading."
        )

    raw_resolution = mapping.get("resolution")
    resolution = (
        None
        if raw_resolution is None
        else _resolution(_record(raw_resolution, f"{where} resolution"), f"{where} resolution")
    )
    if resolution is not None and resolution.arbiter_id in readers:
        raise ValueError(
            f"{where} names {resolution.arbiter_id!r} as its arbiter, and that "
            f"is one of its two annotators ({readers}). The arbiter is the "
            "third reader: an arbiter who is one of the two has not arbitrated "
            "anything, they have read the item twice, and the agreement number "
            "over this item would be a statement about that reader alone."
        )

    locator = mapping.get("comment_locator")
    if locator is not None and not isinstance(locator, dict):
        raise ValueError(
            f"{where} has no usable 'comment_locator': {locator!r}. The "
            "comment's own address is either the chain's locator or nothing."
        )

    return GoldItem(
        item_id=item_id,
        project_id=_text(mapping, "project_id", where),
        version_id=_text(mapping, "version_id", where),
        feedback_id=_text(mapping, "feedback_id", where),
        fixture=_text(mapping, "fixture", where),
        comment_id=_text(mapping, "comment_id", where),
        comment_locator=locator,
        paragraph=_optional_int(mapping, "paragraph", where),
        start=_optional_int(mapping, "start", where),
        end=_optional_int(mapping, "end", where),
        annotations=annotations,
        resolution=resolution,
    )


def _optional_int(mapping: Mapping[str, Any], key: str, where: str) -> int | None:
    """An integer at *key*, or ``None`` when it is absent or null.

    :raises ValueError: when the value is present and is not an integer.
    """
    raw = mapping.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(
            f"{where} has no usable {key!r}: {raw!r}. An offset is a number, and a "
            "number that is not one cannot address anything."
        )
    return int(raw)


def validate_manifest(data: Mapping[str, Any]) -> GoldManifest:
    """The manifest, read and checked.

    **Every rule the manifest has, applied here.** A label outside the
    closed set, a project in two partitions, two readings by one annotator,
    a reading with no annotator or no moment, an item id used twice — each
    is refused by name, with the offending value in the message.

    **Structure and completeness are two different checks.** This one says
    the manifest is well formed; :func:`require_annotated` says the gold
    set is finished. A manifest whose readings are missing is still a
    manifest — that is the one T02 dispatches — and it is this function
    that has to be able to read it.

    :raises ValueError: when the manifest breaks one of its rules.
    """
    version = _text(data, "version", "the manifest")

    raw_corpus = _require(data, "corpus", "the manifest")
    if not isinstance(raw_corpus, dict):
        raise ValueError(
            f"the manifest has no usable 'corpus': {raw_corpus!r}. The corpus is "
            "the material the items read, and a manifest that does not say which "
            "material cannot be checked against it."
        )

    raw_partitions = _require(data, "partitions", "the manifest")
    if not isinstance(raw_partitions, dict):
        raise ValueError(
            f"the manifest has no usable 'partitions': {raw_partitions!r}. The "
            "split is by project, and a manifest that does not carry the split "
            "cannot be split."
        )
    partitions: dict[str, tuple[str, ...]] = {}
    where_project: dict[str, str] = {}
    for name, members in raw_partitions.items():
        if not isinstance(members, list):
            raise ValueError(
                f"partition {name!r} holds {members!r}, and a partition holds a "
                "list of projects. The split is by project, so the list is the "
                "split."
            )
        projects: list[str] = []
        for member in members:
            if not isinstance(member, str) or not member.strip():
                raise ValueError(
                    f"partition {name!r} holds {member!r}, which is not a project "
                    "id. A partition names projects, and a name that is not one "
                    "puts nothing in it."
                )
            if member in where_project:
                raise ValueError(
                    f"project {member!r} is in partitions {where_project[member]!r} "
                    f"and {name!r}. Two versions of one paper are two "
                    "observations of one thing, so every row of one project is "
                    "in the same partition; a project in two partitions would "
                    "put version 1 in one split and version 2 in the other, and "
                    "a system that memorised version 1 would score on version 2 "
                    "without having generalised."
                )
            where_project[member] = name
            projects.append(member)
        partitions[name] = tuple(projects)

    raw_items = _require(data, "items", "the manifest")
    if not isinstance(raw_items, list):
        raise ValueError(
            f"the manifest has no usable 'items': {raw_items!r}. The items are "
            "the entries, and a manifest of entries that are not a list is a "
            "manifest of nothing."
        )

    items: list[GoldItem] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise ValueError(
                f"item {index} is {raw!r}, and an item is a record of a comment. "
                "The manifest is a list of records, and a record that is not one "
                "cannot be read."
            )
        item = _item(raw, index)
        if item.item_id in seen:
            raise ValueError(
                f"item {item.item_id!r} appears twice. An id is minted once, and "
                "a second row wearing one name would be counted twice."
            )
        seen.add(item.item_id)
        if item.project_id not in where_project:
            raise ValueError(
                f"item {item.item_id!r} names project {item.project_id!r}, and "
                "that project is in no partition. The split is by project, so an "
                "item outside every partition is an item nobody can train on and "
                "nobody can test on."
            )
        items.append(item)

    return GoldManifest(
        version=version,
        corpus={
            name: dict(_record(entry, f"corpus entry {name!r}"))
            for name, entry in raw_corpus.items()
        },
        partitions=partitions,
        items=tuple(items),
    )


def require_annotated(manifest: GoldManifest) -> None:
    """The gold set is finished: every item has two readings and a resolution.

    **This is a separate check on purpose.** A manifest whose structure is
    sound but whose readings are missing is a *manifest*, and it is what
    T02 dispatches; this function says whether the *gold set* is done.
    Conflating them would mean a manifest shipped with no annotations in it
    could not be read at all — and a manifest nobody can read is not a
    manifest waiting to be filled in.

    :raises ValueError: naming every item that is short and what it is
        short of. **Every one of them, not the first**: a reviewer wants
        to know how much is left, not to be stopped at the first.
    """
    missing: list[str] = []
    for item in manifest.items:
        if len(item.annotations) != ANNOTATORS_PER_ITEM:
            missing.append(
                f"{item.item_id!r} carries {len(item.annotations)} annotation(s) "
                f"and needs {ANNOTATORS_PER_ITEM}"
            )
        if item.resolution is None:
            missing.append(f"{item.item_id!r} has no resolution")
    if missing:
        raise ValueError(
            "the gold set is not finished. " + "; ".join(missing) + ". The "
            "readings are a person's work, and a manifest that says the "
            "arbiter settled every disagreement nobody could settle is a "
            "manifest that lies about its own completeness."
        )


def load_manifest(path: Path | None = None) -> GoldManifest:
    """The manifest in the tree, read and checked.

    :raises ValueError: when the file is not there, is not JSON, or breaks
        one of the manifest's rules.
    """
    target = MANIFEST_RELATIVE_PATH if path is None else path
    if not target.is_file():
        raise ValueError(
            f"the manifest is not at {target}. A gold set that nobody can read "
            "is not a gold set, and the file's absence is the first thing a "
            "reader should be told."
        )
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"the manifest at {target} is not JSON: {error}. A manifest that "
            "cannot be parsed cannot be read, and a reader that guessed at the "
            "shape would be reading something else."
        ) from error
    if not isinstance(raw, dict):
        raise ValueError(
            f"the manifest at {target} is {type(raw).__name__}, and a manifest "
            "is a record of its own contents."
        )
    return validate_manifest(raw)


def agreement(manifest: GoldManifest) -> Agreement:
    """How far the two annotators agreed, and over what.

    **The denominator is the number of items both annotators labelled** —
    not the number of items in the manifest, and not the number either
    annotator labelled. The manifest requires two readings per item, so
    that number is the manifest's item count here, and it is named in
    :attr:`Agreement.denominator_meaning` so a reader of the number knows
    what it counted.

    **``UNKNOWN`` is in the distribution and not filtered out of it.** It is
    an answer, and a set of answers that drops the honest ones is a set
    that reports more agreement than the two readers had.
    """
    if not manifest.items:
        raise ValueError(
            "the manifest holds no item, and an agreement over no item is not "
            "an agreement. The number would be zero, and zero is a claim that "
            "they disagreed about everything."
        )
    for item in manifest.items:
        if len(item.annotations) != ANNOTATORS_PER_ITEM:
            raise ValueError(
                f"item {item.item_id!r} carries {len(item.annotations)} "
                f"annotation(s), and the agreement is computed over items both "
                f"annotators labelled, which means {ANNOTATORS_PER_ITEM} of them. "
                "An item with one reading is not in the denominator, and the "
                "denominator is part of the answer."
            )

    views: dict[str, LabelAgreement] = {}
    for address in ADDRESSES:
        for axis in AnnotationAxis:
            view = f"{address}.{axis.value}"
            agreed = 0
            for item in manifest.items:
                left = _labels_of(item.annotations[0], address).as_mapping()[axis.value]
                right = _labels_of(item.annotations[1], address).as_mapping()[axis.value]
                if left == right:
                    agreed += 1
            views[view] = LabelAgreement(
                view=view,
                agreed=agreed,
                denominator=len(manifest.items),
            )

    fully = 0
    for item in manifest.items:
        if all(
            _labels_of(item.annotations[0], address).agrees_with(
                _labels_of(item.annotations[1], address)
            )
            for address in ADDRESSES
        ):
            fully += 1

    distribution: dict[str, dict[str, int]] = {}
    for address in ADDRESSES:
        for item in manifest.items:
            for annotation in item.annotations:
                for name, label in _labels_of(annotation, address).as_mapping().items():
                    key = f"{address}.{name}"
                    counts = distribution.setdefault(key, {})
                    counts[label] = counts.get(label, 0) + 1

    return Agreement(
        denominator=len(manifest.items),
        denominator_meaning=(
            "the number of items both annotators labelled, which is every item "
            "in the manifest: the manifest requires two independent readings "
            "per item and refuses an item without them"
        ),
        fully_agreed=fully,
        per_view=views,
        distribution=distribution,
    )


def _labels_of(annotation: Annotation, address: str) -> AddressLabels:
    """The labels of one address of one annotation."""
    if address == "comment_address":
        return annotation.comment_address
    if address == "body_address":
        return annotation.body_address
    raise ValueError(
        f"{address!r} is not an address of a comment. A comment has two: {', '.join(ADDRESSES)}."
    )


def unknown_share(agreement_report: Agreement, view: str) -> float | None:
    """How much of one view's answers were ``UNKNOWN``, or ``None`` if there were none.

    **A share, and not a count.** The number that matters is the fraction
    of the readings that were honest doubts, because a view that is mostly
    ``UNKNOWN`` says the corpus is hard to read rather than that the
    annotators agreed.
    """
    counts = agreement_report.distribution.get(view)
    if not counts:
        return None
    total = sum(counts.values())
    if total == 0:
        return None
    return counts.get(UNKNOWN, 0) / total


__all__ = [
    "ADDRESSES",
    "ANNOTATORS_PER_ITEM",
    "MANIFEST_RELATIVE_PATH",
    "AddressLabels",
    "Agreement",
    "Annotation",
    "GoldItem",
    "GoldManifest",
    "LabelAgreement",
    "Resolution",
    "agreement",
    "load_manifest",
    "require_annotated",
    "unknown_share",
    "validate_manifest",
]
