"""Witnessed machinery for LC-P2-14's human rating close-out.

**Why this module is in the tree while the sheets are not.** The scaled run's
answer volumes, the raters' sheets and the unblinding map carry material or
answers and live outside the repository. This module carries no such content:
it holds only the *shape* of an anonymous volume, the order in which two
raters see those volumes, the agreement check, the arbiter's door, and the
three paired sign tests. The scripts outside the tree feed it the real files;
the witnesses in ``tests/test_blind_evaluation_preparation.py`` feed it
invented ones.

**What an evidence record may not carry.** A blind sheet is allowed to carry
an anonymous volume id, an answer body and the five rating columns. It is
not allowed to carry an arm, a case key, a rater identity, an annotator id,
a hidden answer route, or any field whose value comes from the unblinding
map. :func:`assemble_rating_sheets` enforces that with an allow-list, and
:func:`assert_anonymous_sheets` checks the *values* of the withheld mapping
against the sheets' structural fields, so a leak through an unexpected field
name is caught too. The answer body itself is not scanned for ordinary words:
a rater must be able to read it.

**Where independence is checked.** Two raters are two independent readings
only if they read the same complete set in different orders and no rating is
inferred from the other's sheet. The two sheets are built from separate
seeds; :func:`load_rating_sheet` refuses a missing, duplicated, extra or
unrated item and refuses a label outside the protocol's three. Unblinding is
a third act, after both sheets are complete.

**What may be concluded.** The close-out refuses to aggregate until every
disagreement has a third reader's label. It then pairs C/D, D/E and the
protocol's arrangement pair (``B+critique`` against ``B-only``) by case, and
uses the protocol's exact two-tailed sign test for all three. A verdict that
is not significant is reported as not significant; nothing in this module
rewrites a verdict after the test has spoken.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .blind_sheet import (
    DIMENSIONS,
    RATING_LABELS,
    BlindSheet,
    BlindSheetItem,
    ExcludedRating,
    ResolvedRating,
    resolve_pair,
)
from .significance import (
    ContrastReport,
    DimensionRow,
    assess_significance,
    pair_by_case,
    render_report,
)

#: The fields a rater may see. Anything else is a route back to the answer:
#: an arm, a case key, a name, a source path, a prompt, or a mapping entry.
BLIND_SHEET_KEYS: Final[frozenset[str]] = frozenset({"sheet_id", "rater", "items"})
COMPLETED_SHEET_KEYS: Final[frozenset[str]] = frozenset({"sheet_id", "rater", "rated", "items"})
BLIND_ITEM_KEYS: Final[frozenset[str]] = frozenset({"item_id", "answer", "ratings"})

#: Field names and values that must never appear in a blind sheet's
#: structural fields. The values are read from the withheld map at check time.
FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "arm",
        "arm_id",
        "arm_key",
        "assigned_arm",
        "case",
        "case_id",
        "issue_key",
        "annotator_id",
        "answer_route",
        "source_id",
        "source",
        "mapping",
        "unblinding",
        "notice",
        "deanonymized",
    }
)

#: The prefix of an anonymous volume id. Its suffix is a salted digest, not
#: an index: an id that says which call produced the answer is a route back
#: to the arm and case. The two rater ids are role labels, not people's names.
VOLUME_ID_PREFIX: Final = "volume-"
_IDENTIFIER = re.compile(r"\Avolume-[0-9a-f]{16}\Z")
_ID_NAMESPACE_PREFIX: Final = "labcairn.blind.rating.v1"

RATER_A: Final = "rater-a"
RATER_B: Final = "rater-b"
SHEET_ID_A: Final = "lc-p2-14-rater-a"
SHEET_ID_B: Final = "lc-p2-14-rater-b"

#: The default salt and seeds make the witnesses deterministic. The assembly
#: script passes a fresh salt and two fresh seeds for the real sheets.
DEFAULT_NAMESPACE: Final = "witness-namespace"
SEED_A: Final = 2026110401
SEED_B: Final = 2026110402

#: The three contrasts the close-out computes: the two the work order names,
#: and the arrangement pair the protocol names as its third comparison
#: ("B+C does not beat B-only" is the finding, not a failure of the run).
#: Their arms and cases are read only from the unblinding map, at close-out,
#: never from a rating sheet.
CONTRASTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("D vs C", "D", "C"),
    ("E vs D", "E", "D"),
    ("B+C vs B-only", "B+critique", "B-only"),
)

ARBITER_FIELD: Final = "arbitrations"

#: The protocol's own denominator rule, per dimension. Four dimensions are
#: measured only where their evidence exists; hallucination and mis-citation
#: is measured on every case. A close-out without this mask would silently
#: turn every dimension into "every rated case", which is not the protocol.
DENOMINATOR_FIELD: Final = "denominators"
HALLUCINATION_DIMENSION: Final = "hallucination_mis_citation"


class RatingRefusedError(ValueError):
    """A scoring input is incomplete, inconsistent or no longer blind."""


@dataclass(frozen=True, slots=True)
class AnswerVolume:
    """One answer body and its withheld placement, before anonymisation."""

    source_id: str
    answer: str
    arm: str
    case: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.answer.strip():
            raise RatingRefusedError("an answer volume carries no id or no body")
        if not self.arm or not self.case:
            raise RatingRefusedError(f"answer volume {self.source_id} has no arm or case")


@dataclass(frozen=True, slots=True)
class UnblindingEntry:
    """One anonymous volume's arm and case, withheld until close-out."""

    arm: str
    case: str


@dataclass(frozen=True, slots=True)
class AgreementReport:
    """The two independent readings' agreement, with its denominator."""

    compared: int
    agreed: int
    disagreements: tuple[tuple[str, str], ...]

    @property
    def rate(self) -> float | None:
        """The agreement rate, or None when its denominator is zero."""
        if self.compared == 0:
            return None
        return self.agreed / self.compared


@dataclass(frozen=True, slots=True)
class CloseoutReport:
    """The settled ratings, their exclusions and both rendered contrasts."""

    agreement: AgreementReport
    resolved: tuple[ResolvedRating, ...]
    excluded: tuple[ExcludedRating, ...]
    reports: tuple[ContrastReport, ...]

    def render(self) -> str:
        """Render the agreement denominator and every contrast row."""
        lines = [
            f"Independent ratings: {self.agreement.agreed}/{self.agreement.compared} "
            f"labels agreed ({len(self.agreement.disagreements)} disagreements).",
            f"Settled labels: {len(self.resolved)}; excluded: {len(self.excluded)}.",
        ]
        lines.extend(summarise_verdicts(self.reports))
        lines.extend(render_report(report) for report in self.reports)
        return "\n".join(lines)


def _require_str(row: Mapping[str, Any], key: str, where: str) -> str:
    """One required string field, refused rather than coerced."""
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise RatingRefusedError(f"{where} carries no {key}")
    return value


def build_volumes(
    rows: Sequence[Mapping[str, Any]],
    answer_body: Mapping[str, str],
) -> tuple[AnswerVolume, ...]:
    """Read completed call rows and their answer bodies, without writing back.

    The arrangement pair's two variants share the letter ``B``. Their roles
    separate them into distinct arm keys, so a later pairing cannot mistake
    two answers to one case for one arm answering twice. A row that is not
    ``ok`` is refused: a partial run does not produce a partial blind sheet.
    A case key or source id quoted inside an answer body is a route back to
    the answer; the route token is redacted before a rater sees the body.
    """
    if not rows:
        raise RatingRefusedError("the run carries no call rows")
    case_ids = sorted({str(row["case"]) for row in rows if isinstance(row.get("case"), str)})
    source_ids = sorted(
        str(row["answer_file"]).removesuffix(".txt")
        for row in rows
        if isinstance(row.get("answer_file"), str)
    )
    volumes: list[AnswerVolume] = []
    seen: set[str] = set()
    for row in rows:
        where = f"call {row.get('call', '?')}"
        if row.get("status") != "ok":
            raise RatingRefusedError(f"{where} is not complete")
        name = _require_str(row, "answer_file", where)
        if name in seen:
            raise RatingRefusedError(f"{where} repeats answer file {name}")
        seen.add(name)
        text = answer_body.get(name)
        if not isinstance(text, str) or not text.strip():
            raise RatingRefusedError(f"{where} has no answer body for {name}")
        for source_id in source_ids:
            text = text.replace(source_id, "[source-id redacted]")
        for case_id in case_ids:
            text = text.replace(case_id, "[case-key redacted]")
        group = _require_str(row, "group", where)
        case = _require_str(row, "case", where)
        raw_arm = _require_str(row, "arm", where)
        roles = row.get("roles")
        if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
            raise RatingRefusedError(f"{where} carries no roles list")
        if group == "arrangement_pair":
            arm = "B+critique" if "independent_critique" in roles else "B-only"
        elif group == "five_arm":
            arm = raw_arm
        else:
            raise RatingRefusedError(f"{where} names an unknown group {group!r}")
        volumes.append(
            AnswerVolume(
                source_id=name.removesuffix(".txt"),
                answer=text,
                arm=arm,
                case=case,
            )
        )
    if len({volume.source_id for volume in volumes}) != len(volumes):
        raise RatingRefusedError("two answer volumes carry the same source id")
    return tuple(volumes)


def _volume_id(namespace: str, source_id: str) -> str:
    """A salted, content-free id for one volume."""
    material = f"{_ID_NAMESPACE_PREFIX}\x00{namespace}\x00{source_id}".encode()
    return f"{VOLUME_ID_PREFIX}{hashlib.sha256(material).hexdigest()[:16]}"


def _shuffled(count: int, seed: int) -> list[int]:
    """One rater's order over the same complete set of volume indexes."""
    order = list(range(count))
    random.Random(seed).shuffle(order)
    return order


def _anonymous_sheet(
    sheet_id: str,
    rater: str,
    volumes: Sequence[AnswerVolume],
    ids: Sequence[str],
    seed: int,
) -> dict[str, Any]:
    """Render one rater's sheet: answer bodies, no mapping, one fixed schema."""
    return {
        "sheet_id": sheet_id,
        "rater": rater,
        "items": [
            {
                "item_id": ids[index],
                "answer": volumes[index].answer,
                "ratings": dict.fromkeys(DIMENSIONS, "unknown"),
            }
            for index in _shuffled(len(volumes), seed)
        ],
    }


def make_leak_vocabulary(unblinding: Mapping[str, Any]) -> dict[str, Any]:
    """Build the check-time token list, without the id-to-placement map.

    A consistency checker needs to know which anonymous ids exist and which
    strings must not appear beside an answer. It does **not** need to know
    which id belongs to which arm or case. This vocabulary therefore carries
    flat lists: no ``items`` mapping, no id paired with a placement, and no
    route from a rater's evidence file back to the answer.
    """
    items = unblinding.get("items")
    if not isinstance(items, Mapping) or not items:
        raise RatingRefusedError("the unblinding map carries no items")
    forbidden: set[str] = set(FORBIDDEN_FIELD_NAMES)
    source_ids: set[str] = set()
    case_ids: set[str] = set()
    for entry in items.values():
        if not isinstance(entry, Mapping):
            raise RatingRefusedError("an unblinding entry is not an object")
        for key, value in entry.items():
            if not isinstance(value, str) or not value:
                continue
            forbidden.add(value)
            if key == "source_id":
                source_ids.add(value)
            if key == "case":
                case_ids.add(value)
    return {
        "item_ids": sorted(str(item_id) for item_id in items),
        "forbidden_values": sorted(forbidden),
        "source_ids": sorted(source_ids),
        "case_ids": sorted(case_ids),
        "notice": "No anonymous id is paired with an arm or case in this file.",
    }


def assemble_rating_sheets(
    volumes: Sequence[AnswerVolume],
    *,
    namespace: str = DEFAULT_NAMESPACE,
    seed_a: int = SEED_A,
    seed_b: int = SEED_B,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Assemble two independently ordered sheets and the withheld map.

    The map holds arm/case/source metadata; the sheets hold only the answer
    body, an anonymous id and the five rating columns. Both sheets cover the
    same volumes. Their orders are shuffled with different seeds.

    ``unknown`` is a rating *label*, not a blank: the assembly writes it so
    the sheet is complete in shape, while a human rater must still replace
    every one with a considered label. :func:`load_rating_sheet` refuses a
    sheet whose ``unknown`` values have not been confirmed by ``rated``.
    """
    if not volumes:
        raise RatingRefusedError("there are no answer volumes to rate")
    if not namespace:
        raise RatingRefusedError("the anonymous ids carry no salt")
    if seed_a == seed_b:
        raise RatingRefusedError("the two raters must not receive the same volume order")
    ids = [_volume_id(namespace, volume.source_id) for volume in volumes]
    if len(set(ids)) != len(ids):
        raise RatingRefusedError("two answer volumes received the same anonymous id")
    sheet_a = _anonymous_sheet(SHEET_ID_A, RATER_A, volumes, ids, seed_a)
    sheet_b = _anonymous_sheet(SHEET_ID_B, RATER_B, volumes, ids, seed_b)
    unblinding = {
        "notice": (
            "Withhold this file from both raters and the arbiter until the "
            "two sheets and every arbitration are complete."
        ),
        "items": {
            item_id: {
                "source_id": volume.source_id,
                "arm": volume.arm,
                "case": volume.case,
            }
            for item_id, volume in zip(ids, volumes, strict=True)
        },
    }
    assert_anonymous_sheets(sheet_a, sheet_b, make_leak_vocabulary(unblinding))
    return sheet_a, sheet_b, unblinding


def assert_anonymous_sheets(
    sheet_a: Mapping[str, Any],
    sheet_b: Mapping[str, Any],
    leak_vocabulary: Mapping[str, Any],
) -> None:
    """Refuse either sheet if it exposes a withheld value or repeats the order.

    The key check is an allow-list: a new field with an innocuous name is
    still a leak if it carries an arm. The value check searches the sheets'
    structural fields for a flat vocabulary of forbidden strings. The
    vocabulary carries no id-to-placement pairs, so the consistency check
    can run before unblinding. It does not scan the answer body for ordinary
    words, since a rater has to read that body; it does refuse a source id
    smuggled into it. The volume ids themselves are allowed, because they
    are the anonymous addresses both raters need.
    """
    raw_ids = leak_vocabulary.get("item_ids")
    raw_forbidden = leak_vocabulary.get("forbidden_values")
    raw_sources = leak_vocabulary.get("source_ids")
    raw_cases = leak_vocabulary.get("case_ids")
    if "items" in leak_vocabulary:
        raise RatingRefusedError("the consistency check must not receive the unblinding map itself")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise RatingRefusedError("the leak vocabulary carries no anonymous ids")
    if (
        not isinstance(raw_forbidden, list)
        or not isinstance(raw_sources, list)
        or not isinstance(raw_cases, list)
    ):
        raise RatingRefusedError("the leak vocabulary carries no forbidden words")
    item_ids = {str(item_id) for item_id in raw_ids}
    forbidden = {str(value) for value in raw_forbidden}
    source_ids = {str(value) for value in raw_sources}
    case_ids = {str(value) for value in raw_cases}
    sheets = (("rater-a", sheet_a), ("rater-b", sheet_b))
    orders: list[tuple[str, ...]] = []
    for label, sheet in sheets:
        if set(sheet) != BLIND_SHEET_KEYS:
            raise RatingRefusedError(f"{label} carries fields outside the anonymous schema")
        items = sheet.get("items")
        if not isinstance(items, list) or not items:
            raise RatingRefusedError(f"{label} carries no items")
        ids: list[str] = []
        structural: list[str] = [str(sheet.get("sheet_id")), str(sheet.get("rater"))]
        for item in items:
            if not isinstance(item, Mapping) or set(item) != BLIND_ITEM_KEYS:
                raise RatingRefusedError(f"{label} has an item outside the anonymous schema")
            item_id = item.get("item_id")
            if not isinstance(item_id, str) or _IDENTIFIER.fullmatch(item_id) is None:
                raise RatingRefusedError(f"{label} carries a non-anonymous item id")
            answer = item.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                raise RatingRefusedError(f"{label} has an item with no answer body")
            ratings = item.get("ratings")
            if not isinstance(ratings, Mapping) or set(ratings) != set(DIMENSIONS):
                raise RatingRefusedError(f"{label} has an item without the five rating columns")
            if any(value not in RATING_LABELS for value in ratings.values()):
                raise RatingRefusedError(f"{label} has a rating outside the label vocabulary")
            ids.append(item_id)
            structural.append(item_id)
            structural.extend(str(key) for key in ratings)
            structural.extend(str(value) for value in ratings.values())
            for key, value in item.items():
                if key != "answer" and isinstance(value, str):
                    structural.append(value)
            for source_id in source_ids:
                if source_id in answer:
                    raise RatingRefusedError(f"{label} carries a source id in an answer body")
            for case_id in case_ids:
                if case_id in answer:
                    raise RatingRefusedError(f"{label} carries a case key in an answer body")
        if len(set(ids)) != len(ids) or set(ids) != item_ids:
            raise RatingRefusedError(f"{label} does not cover exactly the withheld volumes")
        for token in forbidden:
            for value in structural:
                leaked = value == token if len(token) == 1 else token in value
                if leaked:
                    raise RatingRefusedError(f"{label} leaks a withheld value into the blind sheet")
        orders.append(tuple(ids))
    if orders[0] == orders[1]:
        raise RatingRefusedError("the two raters received the same volume order")


def load_rating_sheet(
    document: Mapping[str, Any],
    expected_item_ids: Sequence[str],
    *,
    rater: str,
) -> BlindSheet:
    """Load a completed human sheet, refusing any default or missing rating.

    ``rated`` is the human's confirmation that every ``unknown`` left on the
    sheet is a considered label, not an untouched placeholder. Without it,
    the close-out refuses the sheet rather than silently scoring the
    assembly defaults. The loader also refuses arm keys and extra items.
    """
    if document.get("rater") != rater:
        raise RatingRefusedError(f"the sheet is not {rater}'s completed sheet")
    if set(document) != COMPLETED_SHEET_KEYS:
        raise RatingRefusedError(f"{rater}'s sheet carries fields outside the completed schema")
    if document.get("rated") is not True:
        raise RatingRefusedError(f"{rater}'s sheet is not confirmed as rated")
    items = document.get("items")
    if not isinstance(items, list) or not items:
        raise RatingRefusedError(f"{rater}'s sheet carries no items")
    expected_ids: set[str] = set(expected_item_ids)
    stripped_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping) or set(item) != BLIND_ITEM_KEYS:
            raise RatingRefusedError(f"{rater}'s sheet has an item outside the completed schema")
        if item.get("item_id") not in expected_ids:
            raise RatingRefusedError(f"{rater}'s sheet carries an unexpected item")
        answer = item.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise RatingRefusedError(f"{rater}'s sheet has an item with no answer body")
        stripped_items.append({"item_id": item.get("item_id"), "ratings": item.get("ratings")})
    if (
        len(stripped_items) != len(expected_ids)
        or {str(item["item_id"]) for item in stripped_items} != expected_ids
    ):
        raise RatingRefusedError(f"{rater}'s sheet does not cover exactly the expected volumes")
    sheet_id = document.get("sheet_id")
    if not isinstance(sheet_id, str) or not sheet_id:
        raise RatingRefusedError(f"{rater}'s sheet carries no sheet_id")
    loaded_items: list[BlindSheetItem] = []
    for item in stripped_items:
        ratings = item["ratings"]
        if not isinstance(ratings, Mapping) or set(ratings) != set(DIMENSIONS):
            raise RatingRefusedError(f"{rater}'s sheet has an item without five ratings")
        if any(value not in RATING_LABELS for value in ratings.values()):
            raise RatingRefusedError(f"{rater}'s sheet has a rating outside the vocabulary")
        loaded_items.append(
            BlindSheetItem(
                item_id=str(item["item_id"]),
                ratings={str(key): str(value) for key, value in ratings.items()},
            )
        )
    return BlindSheet(sheet_id=sheet_id, rater=rater, items=tuple(loaded_items))


def expected_ids_from_sheet(document: Mapping[str, Any], *, rater: str) -> tuple[str, ...]:
    """Derive the complete set of anonymous ids from the first rater's sheet.

    The consistency check must not read the unblinding map to know what to
    compare: the two blind readings are checked *before* unblinding. This
    reader refuses an id that is not anonymous, or a list with duplicates.
    """
    if document.get("rater") != rater:
        raise RatingRefusedError(f"the sheet is not {rater}'s completed sheet")
    items = document.get("items")
    if not isinstance(items, list) or not items:
        raise RatingRefusedError(f"{rater}'s sheet carries no items")
    ids: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise RatingRefusedError(f"{rater}'s sheet has a malformed item")
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or _IDENTIFIER.fullmatch(item_id) is None:
            raise RatingRefusedError(f"{rater}'s sheet carries a non-anonymous item id")
        ids.append(item_id)
    if len(set(ids)) != len(ids):
        raise RatingRefusedError(f"{rater}'s sheet carries a duplicate item id")
    return tuple(ids)


def _answer_bodies(document: Mapping[str, Any], *, rater: str) -> dict[str, str]:
    """One sheet's anonymous id to answer body, for cross-sheet integrity."""
    items = document.get("items")
    if not isinstance(items, list):
        raise RatingRefusedError(f"{rater}'s sheet carries no items")
    bodies: dict[str, str] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise RatingRefusedError(f"{rater}'s sheet has a malformed item")
        item_id, answer = item.get("item_id"), item.get("answer")
        if not isinstance(item_id, str) or not isinstance(answer, str):
            raise RatingRefusedError(f"{rater}'s sheet has an item without an id or body")
        if item_id in bodies:
            raise RatingRefusedError(f"{rater}'s sheet repeats item {item_id}")
        bodies[item_id] = answer
    return bodies


def consistency_check(
    sheet_a_document: Mapping[str, Any],
    sheet_b_document: Mapping[str, Any],
) -> tuple[AgreementReport, BlindSheet, BlindSheet]:
    """Check two independent blind readings before any unblinding happens.

    Both sheets must be complete and cover the same anonymous volumes. The
    two answer bodies are compared before the ratings are compared: two
    readings of different texts would be an agreement about nothing. The
    returned disagreement list is the third reader's work list: it names only
    an anonymous id and a dimension, never an arm, case or source.
    """
    answers_a = _answer_bodies(sheet_a_document, rater=RATER_A)
    answers_b = _answer_bodies(sheet_b_document, rater=RATER_B)
    if answers_a != answers_b:
        raise RatingRefusedError("the two sheets do not carry the same answer bodies")
    expected = expected_ids_from_sheet(sheet_a_document, rater=RATER_A)
    sheet_a = load_rating_sheet(sheet_a_document, expected, rater=RATER_A)
    sheet_b = load_rating_sheet(sheet_b_document, expected, rater=RATER_B)
    return compare_ratings(sheet_a, sheet_b), sheet_a, sheet_b


def compare_ratings(sheet_a: BlindSheet, sheet_b: BlindSheet) -> AgreementReport:
    """Compare two complete independent readings, with their denominator."""
    by_b = {item.item_id: item for item in sheet_b.items}
    by_a = {item.item_id: item for item in sheet_a.items}
    if len(by_b) != len(sheet_b.items) or len(by_a) != len(sheet_a.items):
        raise RatingRefusedError("a sheet has duplicate items")
    if set(by_a) != set(by_b):
        raise RatingRefusedError("the two raters did not rate the same volumes")
    agreed = 0
    compared = 0
    disagreements: list[tuple[str, str]] = []
    for item_id in sorted(by_a):
        one, two = by_a[item_id], by_b[item_id]
        for dimension in DIMENSIONS:
            compared += 1
            if one.ratings[dimension] == two.ratings[dimension]:
                agreed += 1
            else:
                disagreements.append((item_id, dimension))
    return AgreementReport(
        compared=compared,
        agreed=agreed,
        disagreements=tuple(disagreements),
    )


def load_arbitrations(
    document: Mapping[str, Any],
    disagreements: Sequence[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    """Read the third reader's labels, refusing an incomplete arbitration.

    Every disagreement must have exactly one label from the protocol's
    vocabulary. A missing decision is refused rather than treated as
    agreement; an extra decision is refused as a decision about a rating
    that was not in dispute. The reader id is machine-checked against the
    two rater ids so an arbiter cannot be one of the two readings; whether
    the person behind that id is actually a third reader is the owner's
    human step, recorded in ``docs/acceptance``.
    """
    reader = document.get("reader")
    if not isinstance(reader, str) or not reader:
        raise RatingRefusedError("the arbiter document carries no reader id")
    if reader in {RATER_A, RATER_B}:
        raise RatingRefusedError("the arbiter must be a third reader, not a rater")
    rows = document.get(ARBITER_FIELD)
    if not isinstance(rows, list):
        raise RatingRefusedError("the arbiter document carries no arbitrations list")
    decisions: dict[tuple[str, str], str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RatingRefusedError("an arbitration is not an object")
        item_id, dimension, label = (
            row.get("item_id"),
            row.get("dimension"),
            row.get("label"),
        )
        if not isinstance(item_id, str) or not isinstance(dimension, str):
            raise RatingRefusedError("an arbitration names no item or dimension")
        if dimension not in DIMENSIONS or not isinstance(label, str) or label not in RATING_LABELS:
            raise RatingRefusedError("an arbitration carries an unknown dimension or label")
        key = (item_id, dimension)
        if key in decisions:
            raise RatingRefusedError(f"the arbiter decided {item_id}/{dimension} twice")
        decisions[key] = label
    expected = set(disagreements)
    missing = sorted(expected - set(decisions))
    extra = sorted(set(decisions) - expected)
    if missing:
        raise RatingRefusedError(
            f"{len(missing)} disagreement(s) have no third-reader arbitration: "
            + ", ".join(f"{item}/{dimension}" for item, dimension in missing[:5])
        )
    if extra:
        raise RatingRefusedError(f"the arbiter decided {len(extra)} agreed rating(s)")
    return decisions


def build_arbitration_packet(
    agreement: AgreementReport,
    sheet_a_document: Mapping[str, Any],
    sheet_b_document: Mapping[str, Any],
    *,
    reader: str = "third-reader",
) -> dict[str, Any]:
    """Build the third reader's blind work list for the disagreements.

    The packet carries only an anonymous item id, a dimension, the answer
    body and the two labels in sorted order. It carries no rater id, arm,
    case or source, so the third reader can settle the boundary question
    without knowing which reading was whose.
    """
    if reader in {RATER_A, RATER_B}:
        raise RatingRefusedError("the arbitration packet must go to a third reader")
    by_a = {item["item_id"]: item for item in sheet_a_document.get("items", [])}
    by_b = {item["item_id"]: item for item in sheet_b_document.get("items", [])}
    items: list[dict[str, Any]] = []
    for item_id, dimension in agreement.disagreements:
        one, two = by_a.get(item_id), by_b.get(item_id)
        if one is None or two is None:
            raise RatingRefusedError(f"disagreement {item_id}/{dimension} has no two answers")
        answer = one.get("answer")
        if not isinstance(answer, str) or answer != two.get("answer"):
            raise RatingRefusedError(f"disagreement {item_id}/{dimension} has inconsistent answers")
        labels = sorted((str(one["ratings"][dimension]), str(two["ratings"][dimension])))
        items.append(
            {
                "item_id": item_id,
                "dimension": dimension,
                "answer": answer,
                "labels": labels,
            }
        )
    return {"reader": reader, "items": items}


def read_unblinding(document: Mapping[str, Any]) -> dict[str, UnblindingEntry]:
    """Read the withheld arm/case map at close-out, refusing an incomplete map."""
    items = document.get("items")
    if not isinstance(items, Mapping) or not items:
        raise RatingRefusedError("the unblinding map carries no items")
    entries: dict[str, UnblindingEntry] = {}
    for item_id, entry in items.items():
        if not isinstance(item_id, str) or _IDENTIFIER.fullmatch(item_id) is None:
            raise RatingRefusedError("the unblinding map carries a non-anonymous item id")
        if not isinstance(entry, Mapping):
            raise RatingRefusedError("an unblinding entry is not an object")
        arm, case = entry.get("arm"), entry.get("case")
        if not isinstance(arm, str) or not isinstance(case, str) or not arm or not case:
            raise RatingRefusedError(f"unblinding entry {item_id} carries no arm or case")
        entries[item_id] = UnblindingEntry(arm=arm, case=case)
    return entries


def verdict_word(significant: bool) -> str:
    """The verdict's own word. Not significant is a first-class outcome."""
    return "SIGNIFICANT" if significant else "NOT SIGNIFICANT"


def summarise_verdicts(reports: Sequence[ContrastReport]) -> tuple[str, ...]:
    """One machine-checkable line per verdict, taken from the verdict itself."""
    lines: list[str] = []
    for report in reports:
        for row in report.rows:
            verdict = row.verdict
            p_value = "n/a" if verdict.p_value is None else f"{verdict.p_value:.4f}"
            lines.append(
                f"{verdict.contrast} on {verdict.dimension}: "
                f"{verdict_word(verdict.significant)}; "
                f"wins={verdict.counts.wins}, losses={verdict.counts.losses}, "
                f"ties={verdict.counts.ties}, p={p_value}"
            )
    return tuple(lines)


def read_denominators(
    document: Mapping[str, Any],
    known_cases: Sequence[str],
) -> dict[str, frozenset[str]]:
    """Read the protocol's own denominator mask, dimension by dimension.

    The mask is human work: it names the cases on which each dimension is
    measurable. It is refused, not defaulted, when a dimension is missing, a
    case is unknown, a case is repeated, or hallucination and mis-citation
    does not cover every case. An empty denominator is allowed for the four
    evidence-bounded dimensions; the sign test will then report not
    significant by rule rather than inventing a rate.
    """
    raw = document.get(DENOMINATOR_FIELD)
    if not isinstance(raw, Mapping):
        raise RatingRefusedError("the denominators document carries no denominators mapping")
    if set(raw) != set(DIMENSIONS):
        raise RatingRefusedError("the denominators mapping must name exactly the five dimensions")
    known = set(known_cases)
    denominators: dict[str, frozenset[str]] = {}
    for dimension in DIMENSIONS:
        rows = raw[dimension]
        if not isinstance(rows, list) or any(not isinstance(case, str) for case in rows):
            raise RatingRefusedError(f"{dimension} has a malformed denominator list")
        if len(set(rows)) != len(rows):
            raise RatingRefusedError(f"{dimension} repeats a case in its denominator")
        unknown = sorted(set(rows) - known)
        if unknown:
            raise RatingRefusedError(
                f"{dimension} names case(s) outside the run: {', '.join(unknown)}"
            )
        if dimension == HALLUCINATION_DIMENSION and set(rows) != known:
            missing = sorted(known - set(rows))
            raise RatingRefusedError(
                "hallucination_mis_citation must cover every case; missing: " + ", ".join(missing)
            )
        denominators[dimension] = frozenset(rows)
    return denominators


def _dimension_row(
    dimension: str,
    resolved: Sequence[ResolvedRating],
    excluded: Sequence[ExcludedRating],
    item_arms: Mapping[str, str],
    item_cases: Mapping[str, str],
    denominator: frozenset[str],
    contrast: str,
    treatment: str,
    control: str,
) -> DimensionRow:
    """One dimension's verdict over its own denominator, not every case."""
    eligible = [
        rating
        for rating in resolved
        if rating.dimension == dimension and item_cases.get(rating.item_id) in denominator
    ]
    eligible_excluded = [
        rating
        for rating in excluded
        if rating.dimension == dimension and item_cases.get(rating.item_id) in denominator
    ]
    counts = pair_by_case(
        eligible,
        item_arms,
        item_cases,
        dimension,
        treatment,
        control,
    )
    agreed = sum(1 for rating in eligible if rating.basis == "agreement")
    arbitrated = sum(1 for rating in eligible if rating.basis == "arbitrated")
    return DimensionRow(
        dimension=dimension,
        verdict=assess_significance(contrast, dimension, counts),
        agreed=agreed,
        arbitrated=arbitrated,
        excluded=len(eligible_excluded),
    )


def _contrast_report(
    contrast: str,
    treatment: str,
    control: str,
    resolved: Sequence[ResolvedRating],
    excluded: Sequence[ExcludedRating],
    item_arms: Mapping[str, str],
    item_cases: Mapping[str, str],
    denominators: Mapping[str, frozenset[str]],
) -> ContrastReport:
    """Build one contrast with each dimension's own denominator."""
    return ContrastReport(
        contrast=contrast,
        rows=tuple(
            _dimension_row(
                dimension,
                resolved,
                excluded,
                item_arms,
                item_cases,
                denominators[dimension],
                contrast,
                treatment,
                control,
            )
            for dimension in DIMENSIONS
        ),
    )


def close_out(
    sheet_a_document: Mapping[str, Any],
    sheet_b_document: Mapping[str, Any],
    arbiter_document: Mapping[str, Any],
    unblinding_document: Mapping[str, Any],
    denominators_document: Mapping[str, Any],
) -> CloseoutReport:
    """Settle the two readings, then compute the protocol's three contrasts.

    The unblinding act happens here, after both sheets are complete and every
    disagreement has a third reader's label. The five-arm contrasts are
    ``D vs C`` and ``E vs D``; the third is the protocol's arrangement pair,
    ``B+C vs B-only`` (the protocol's "role arrangement measured separately
    from the evidence"), paired by case through the same exact two-tailed
    sign test and rendered under the same honesty rule — the protocol's own
    words are that if ``B+C`` does not beat ``B-only``, that is the finding.
    """
    structural_a = {key: sheet_a_document[key] for key in BLIND_SHEET_KEYS}
    structural_b = {key: sheet_b_document[key] for key in BLIND_SHEET_KEYS}
    assert_anonymous_sheets(structural_a, structural_b, make_leak_vocabulary(unblinding_document))
    unblinding = read_unblinding(unblinding_document)
    agreement, sheet_a, sheet_b = consistency_check(sheet_a_document, sheet_b_document)
    if set(unblinding) != {item.item_id for item in sheet_a.items}:
        raise RatingRefusedError("the unblinding map does not cover exactly the rated volumes")
    decisions = load_arbitrations(arbiter_document, agreement.disagreements)
    resolved, excluded = resolve_pair(sheet_a, sheet_b, decisions)
    if excluded:
        raise RatingRefusedError(f"{len(excluded)} rating(s) remain unresolved after arbitration")
    item_arms = {item: entry.arm for item, entry in unblinding.items()}
    item_cases = {item: entry.case for item, entry in unblinding.items()}
    denominators = read_denominators(
        denominators_document,
        sorted({entry.case for entry in unblinding.values()}),
    )
    reports = tuple(
        _contrast_report(
            label,
            treatment,
            control,
            resolved,
            excluded,
            item_arms,
            item_cases,
            denominators,
        )
        for label, treatment, control in CONTRASTS
    )
    return CloseoutReport(
        agreement=agreement,
        resolved=resolved,
        excluded=excluded,
        reports=reports,
    )
