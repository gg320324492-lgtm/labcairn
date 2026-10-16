"""What counts as a placeholder, decided in advance and checkable.

The acceptance rule is *"no empty placeholder passes"*. Left undefined, that rule
is satisfied by whatever the checker happened to look at, so it is written here
as four named, separately testable conditions. Each catches a different way a
stage produces something that looks like work and is not.

1. **Placeholder vocabulary** — a prose field whose normalised text is one of a
   closed set of markers (``TODO``, ``TBD``, ``N/A``, ``待定`` …) says the author
   ran out of things to say. A closed set rather than a regex, because "looks
   like a TODO" is a rule that would otherwise be re-decided by whoever next
   edits the pattern.

2. **Too little substance to carry a claim** — a body field with fewer than
   :data:`MIN_SUBSTANTIVE_CHARS` alphanumeric characters cannot hold a finding.
   This one is a heuristic and is labelled as such. It is the weakest of the
   four, and conditions 3 and 4 are the ones that do not depend on it.

3. **Empty primary collections** — an artifact with no materials, no claims, no
   sections is not a report about nothing. It is a stage that returned an empty
   object, which is the easiest possible way to satisfy an "is the output
   present" check. The fields this applies to are
   :data:`PRIMARY_CONTENT_FIELDS`; the schema already requires each to be
   non-empty, and a test asserts that, so the list says *which invariant
   matters* while the model says *what happens when it is broken*.

4. **Derivation and closure** — an artifact whose ``derived_from`` does not name
   what it was built from, or which cites ids and hashes no upstream stage
   produced, has no relationship to its inputs however substantial its prose is.
   Checked in :mod:`labcairn.skills.execution`, which holds the upstream
   artifacts and their digests; the rules themselves are here, next to the rest
   of the definition, because they are the same acceptance rule and splitting
   them across two modules would make the rule harder to audit than the code.

The honest limit
----------------
Conditions 1-3 are about text, and no text heuristic can tell a real finding from
a fluent paragraph that says nothing. What they do catch is the failure this
acceptance rule is aimed at: a stage that did not do the work and emitted a
shell. The properties that survive a fluent fake are condition 4's — a
well-written section citing claims that were never verified is still refused,
because its ids do not resolve.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Final, get_args, get_origin

from pydantic import BaseModel

from labcairn.core.schema import LabCairnModel
from labcairn.skills.artifacts import (
    ARTIFACT_TYPES,
    ArtifactKind,
    DeliveredReport,
    EvidenceLedgerView,
    ReportDraft,
    ResearchObjective,
    ResearchProposal,
    RetrievedExcerpts,
    SourceInventory,
    StageName,
    ValidationReport,
)
from labcairn.skills.errors import DerivationClosureError, PlaceholderError

#: Minimum alphanumeric characters in a body field. Deliberately low: the point
#: is to reject ``"TODO"`` and ``"..."``, not to enforce a house style.
#: Alphanumeric rather than ``len()`` so it behaves the same for Chinese text,
#: which has no whitespace to split on.
MIN_SUBSTANTIVE_CHARS: Final = 12

#: Closed vocabulary of "I did not fill this in", compared after normalisation.
PLACEHOLDER_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "todo",
        "tbd",
        "to be determined",
        "to be done",
        "to be added",
        "to be written",
        "fixme",
        "xxx",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "placeholder",
        "dummy",
        "lorem ipsum",
        "foo",
        "bar",
        "baz",
        "sample",
        "example only",
        "asdf",
        "???",
        "...",
        "待定",
        "待补充",
        "占位",
        "占位符",
        "暂无",
        "无",
    }
)

#: Free-text fields checked only against the placeholder vocabulary. Headings
#: and names are legitimately short — "Methods" is a real heading — so the
#: length floor does not apply to them.
PROSE_FIELDS: Final[frozenset[str]] = frozenset(
    {"display_name", "heading", "locator_description", "retrieval_method", "note"}
)

#: Fields that must carry enough text to hold a statement, held to both the
#: vocabulary and :data:`MIN_SUBSTANTIVE_CHARS`.
BODY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "body",
        "statement",
        "rationale",
        "reason",
        "message",
        "direction",
        "objective",
        "success_criterion",
        "excerpt",
        "new_value",
        "old_value",
    }
)

#: Identifier-shaped fields. Never subject to a text check: ``claim_id`` holding
#: ``"c1"`` is correct, not a placeholder.
IDENTIFIER_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "task_id",
        "claim_id",
        "item_id",
        "change_id",
        "section_id",
        "finding_id",
        "anchor_id",
        "decision_id",
        "target",
        "target_section_id",
        # Tuples of ids. Their *elements* are identifier-shaped, and the
        # non-emptiness rule for the collections themselves lives in
        # ``PRIMARY_CONTENT_FIELDS``.
        "evidence_refs",
        "checked_sections",
    }
)

#: Pattern- or enum-typed string fields. ``"a" * 64`` is not a short message, it
#: is a sha256; a length floor on it would reject every hash in the system.
FORMAT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        # Pattern-typed digests and the lineage tuple that carries them.
        "content_sha256",
        "material_sha256",
        "extracted_span_sha256",
        "draft_digest",
        "derived_from",
        # Closed string enumerations. ``StrEnum`` members satisfy ``issubclass(x,
        # str)``, so the coverage walk sees them as strings; they are not prose.
        "locator_kind",
        "severity",
        "status",
        "materiality",
        "verdict",
        "validation_verdict",
        "readability",
        # A path. Checking it for placeholders would reject every real filename.
        "relative_path",
    }
)

#: Collections that make an artifact a report rather than an empty shell.
PRIMARY_CONTENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "declared_materials",
        "materials",
        "anchors",
        "excerpts",
        "claims",
        "items",
        "sections",
        "findings",
        "checked_sections",
        "manifest",
        "evidence_refs",
    }
)

_WHITESPACE: Final[re.Pattern[str]] = re.compile(r"\s+")

#: Punctuation stripped from both ends before a vocabulary comparison: ASCII
#: plus the full-width forms, because a report in this project may be written in
#: either, and the Chinese full stop has to match the token sitting beside it.
#:
#: Built from codepoints rather than written literally. These are *data* -- the
#: exact characters to trim -- and spelled as ``chr(...)`` a reader can tell them
#: apart from prose that merely contains full-width punctuation, without the
#: linter having to guess which of the two it is looking at.
_TRIM_CHARS: Final[str] = "".join(
    chr(code)
    for code in (
        0x09,
        0x0A,
        0x0D,
        0x20,  # tab, newline, carriage return, space
        0x2E,
        0x2C,
        0x3B,
        0x3A,
        0x21,
        0x3F,
        0x2D,
        0x5F,  # . , ; : ! ? - _
        0x5B,
        0x5D,
        0x7B,
        0x7D,
        0x28,
        0x29,
        0x3C,
        0x3E,
        0x22,
        0x27,  # brackets, angle brackets, quotes
        0x2026,  # horizontal ellipsis
        0x3001,
        0x3002,  # ideographic comma, ideographic full stop
        0xFF0C,
        0xFF1B,
        0xFF1A,  # fullwidth comma, semicolon, colon
        0xFF01,
        0xFF1F,
        0xFF08,
        0xFF09,  # fullwidth ! ? ( )
        0x300A,
        0x300B,
        0x3010,
        0x3011,  # book-title marks, lenticular brackets
    )
)


def normalize_placeholder_text(value: str) -> str:
    """Casefold, collapse runs of whitespace, strip surrounding punctuation.

    Whitespace *inside* the text is collapsed, so ``"to   be\\tdetermined"``
    matches its marker. Punctuation is stripped only from the ends, so ``"n/a"``
    keeps its slash and ``"a/b"`` is not mistaken for it.
    """
    collapsed = _WHITESPACE.sub(" ", value).strip()
    return collapsed.casefold().strip(_TRIM_CHARS)


def is_placeholder_token(value: str) -> bool:
    """Whether *value* is a marker of "I did not fill this in".

    Two ways to qualify. The obvious one is a normalised match against
    :data:`PLACEHOLDER_TOKENS`. The second is that the value is **nothing but
    punctuation** — ``"???"``, ``"..."``, ``"..."`` — which trims to the empty
    string and therefore matches nothing in the set. That case has to be
    recognised separately: trimming is what makes ``"待定。"`` match ``"待定"``,
    and it would otherwise turn the punctuation-only markers into empty strings
    that read as *not* a marker.
    """
    normalized = normalize_placeholder_text(value)
    if normalized in PLACEHOLDER_TOKENS:
        return True
    return normalized == "" and value.strip() != ""


def substantive_length(value: str) -> int:
    """Count of alphanumeric characters — a language-agnostic "how much is here"."""
    return sum(1 for char in value if char.isalnum())


def iter_text_fields(model: BaseModel, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield ``(dotted_path, value)`` for every string field in a model tree.

    Recurses through nested models and through lists and tuples of models, so a
    placeholder buried in ``sections[2].body`` is found without the caller
    having to know the artifact's shape.
    """
    prefix = f"{path}." if path else ""
    for name in type(model).model_fields:
        value = getattr(model, name, None)
        child = f"{prefix}{name}"
        if isinstance(value, str):
            yield child, value
        elif isinstance(value, BaseModel):
            yield from iter_text_fields(value, child)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if isinstance(item, BaseModel):
                    yield from iter_text_fields(item, f"{child}[{index}]")


# ---------------------------------------------------------------------------
# Field coverage — how "every prose field is checked" stays true
# ---------------------------------------------------------------------------


def _flatten_annotation(annotation: object) -> Iterator[object]:
    yield annotation
    origin = get_origin(annotation)
    if origin is not None:
        for arg in get_args(annotation):
            yield from _flatten_annotation(arg)
    elif hasattr(annotation, "__metadata__"):
        for arg in getattr(annotation, "__args__", ()):
            yield from _flatten_annotation(arg)


def _nested_models(annotation: object) -> Iterator[type[BaseModel]]:
    for candidate in _flatten_annotation(annotation):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            yield candidate


def string_field_names(models: tuple[type[BaseModel], ...]) -> frozenset[str]:
    """Every string field name reachable from *models*, by annotation walk.

    Walks types rather than instances, because building an instance of every
    artifact to ask "what fields does it have" would mean constructing valid
    placeholder data — which is precisely what these models refuse.
    """
    names: set[str] = set()
    seen: set[type[BaseModel]] = set()
    pending: list[type[BaseModel]] = list(models)
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        for name, info in model.model_fields.items():
            if _flatten_annotation(info.annotation):
                nested = tuple(_nested_models(info.annotation))
                if nested:
                    pending.extend(nested)
                    continue
                candidates = _flatten_annotation(info.annotation)
                if any(_is_str_like(candidate) for candidate in candidates):
                    names.add(name)
    return frozenset(names)


def _is_str_like(candidate: object) -> bool:
    """Whether an annotation is ``str``, possibly wrapped in ``Annotated``.

    ``get_origin`` on a bare ``str`` is ``None``, and on ``Annotated[str, ...]``
    the args carry the bare type, so both are covered by looking at the
    annotation and its first type argument.
    """
    return candidate is str or (isinstance(candidate, type) and issubclass(candidate, str))


#: Every model reachable from the artifact table. Used by the coverage test so a
#: new artifact with an unchecked field fails that test rather than quietly
#: shipping a hole in the placeholder rule.
CONTRACT_MODELS: Final[tuple[type[BaseModel], ...]] = tuple(ARTIFACT_TYPES.values())


# ---------------------------------------------------------------------------
# Condition 1-3: substance
# ---------------------------------------------------------------------------


def require_substance(artifact: LabCairnModel) -> None:
    """Refuse an artifact that is a shell.

    :raises PlaceholderError: listing **every** violation rather than the first,
        so one run of a research task reports all of its empty sections at once
        instead of one per attempt, burning the retry budget to find out.
    """
    problems: list[str] = []

    for path, value in iter_text_fields(artifact):
        field_name = _leaf_name(path)
        if field_name in IDENTIFIER_FIELDS or field_name in FORMAT_FIELDS:
            continue
        if field_name not in PROSE_FIELDS and field_name not in BODY_FIELDS:
            continue
        if is_placeholder_token(value):
            problems.append(
                f"{path}={value!r} is a placeholder marker. A field that announces it "
                f"has nothing to say is the output of a stage that did not run."
            )
            continue
        if field_name in BODY_FIELDS and substantive_length(value) < MIN_SUBSTANTIVE_CHARS:
            problems.append(
                f"{path} carries {substantive_length(value)} alphanumeric character(s), "
                f"below the {MIN_SUBSTANTIVE_CHARS} needed to state a finding: {value!r}"
            )

    problems.extend(_empty_collection_problems(artifact))

    if problems:
        raise PlaceholderError(
            f"{type(artifact).__name__} is a placeholder, not a result:\n  - "
            + "\n  - ".join(problems)
        )


def _leaf_name(path: str) -> str:
    return path.rsplit(".", 1)[-1].split("[", 1)[0]


def _empty_collection_problems(artifact: LabCairnModel) -> list[str]:
    problems: list[str] = []
    for name in type(artifact).model_fields:
        if name not in PRIMARY_CONTENT_FIELDS:
            continue
        value = getattr(artifact, name, None)
        if isinstance(value, (list, tuple)) and len(value) == 0:
            problems.append(
                f"{name} is empty. An artifact with no {name.replace('_', ' ')} is not a "
                f"finding of 'nothing found' — it is a stage that returned a shell."
            )
    return problems


# ---------------------------------------------------------------------------
# Condition 4: reference closure
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UpstreamArtifact:
    """One input artifact together with the digest recorded for it.

    Closure rules need the digest as well as the object: "this delivery names a
    different draft" is a fact about a hash, and comparing two models cannot see
    it.
    """

    kind: ArtifactKind
    digest: str
    artifact: LabCairnModel


@dataclass(frozen=True, slots=True)
class Upstream:
    """The artifacts one stage was handed, in the order it was handed them.

    Order is part of the contract: it is the order the digests appeared in, and
    the order a stage must reproduce in its ``derived_from``. The tuple is not
    normalised on read, because "the same lineage" has to mean the same
    sequence -- a lineage whose order is ignored is one that can be rewritten
    without anything noticing.
    """

    entries: tuple[UpstreamArtifact, ...] = ()

    def expect(self, model: type[LabCairnModel]) -> LabCairnModel:
        """The input that is an instance of *model*.

        :raises DerivationClosureError: when no input has that type, which means
            the stage was handed the wrong things and every reference it makes is
            unverifiable.
        """
        for entry in self.entries:
            if isinstance(entry.artifact, model):
                return entry.artifact
        raise DerivationClosureError(
            f"expected a {model.__name__} among the inputs "
            f"{[entry.kind.value for entry in self.entries]}. A closure rule that "
            f"cannot see its upstream artifact cannot check anything."
        )

    def entry(self, kind: ArtifactKind) -> UpstreamArtifact:
        """The input of *kind*.

        :raises DerivationClosureError: rather than ``KeyError`` -- a missing
            upstream artifact is a lineage failure and is reported as one.
        """
        for candidate in self.entries:
            if candidate.kind is kind:
                return candidate
        raise DerivationClosureError(
            f"expected an input of kind {kind.value!r}; got "
            f"{[entry.kind.value for entry in self.entries]}"
        )

    def digests(self) -> tuple[str, ...]:
        """The input digests in hand-over order: what ``derived_from`` must equal."""
        return tuple(entry.digest for entry in self.entries)


ClosureRule = Callable[[LabCairnModel, Upstream], None]


def _require_subset(
    found: tuple[str, ...], allowed: tuple[str, ...] | set[str], what: str, where: str
) -> None:
    allowed_set = set(allowed)
    offending = sorted(set(found) - allowed_set)
    if offending:
        raise DerivationClosureError(
            f"{where} references {what} that no earlier stage produced: {offending}. "
            f"Available: {sorted(allowed_set)}. A section citing a claim outside the "
            f"ledger this run built is a report about something other than what was "
            f"verified."
        )


def _closure_inventory(artifact: LabCairnModel, upstream: Upstream) -> None:
    inventory = artifact
    if not isinstance(inventory, SourceInventory):
        raise DerivationClosureError(f"expected SourceInventory, got {type(inventory).__name__}")
    objective = upstream.expect(ResearchObjective)
    assert isinstance(objective, ResearchObjective)
    produced = set(inventory.material_hashes())
    declared = set(objective.content_hashes())
    if produced == declared:
        return
    details: list[str] = []
    if declared - produced:
        details.append(f"declared by intake but not inventoried: {sorted(declared - produced)}")
    if produced - declared:
        details.append(f"inventoried but never bound to this task: {sorted(produced - declared)}")
    raise DerivationClosureError(
        f"inventory does not reproduce the materials intake declared ({'; '.join(details)}). "
        f"The inventory is what the rest of the run reads; a material it omits is "
        f"invisible downstream and one it invents was never bound to this task."
    )


def _closure_retrieve(artifact: LabCairnModel, upstream: Upstream) -> None:
    excerpts = artifact
    if not isinstance(excerpts, RetrievedExcerpts):
        raise DerivationClosureError(f"expected RetrievedExcerpts, got {type(excerpts).__name__}")
    inventory = upstream.expect(SourceInventory)
    assert isinstance(inventory, SourceInventory)
    allowed = inventory.anchor_index()
    found = excerpts.excerpt_index()
    unknown = sorted(set(found) - set(allowed))
    if unknown:
        raise DerivationClosureError(
            f"retrieve returned excerpts anchored at {unknown}, which the inventory "
            f"does not contain. Known anchors: {sorted(allowed)}. Retrieval that "
            f"surfaces passages from nowhere is indistinguishable from one that "
            f"invented them."
        )
    drifted = sorted(
        f"{anchor_id} (excerpt says {material!r}, inventory says {allowed[anchor_id]!r})"
        for anchor_id, material in found.items()
        if allowed[anchor_id] != material
    )
    if drifted:
        raise DerivationClosureError(
            f"retrieve cites anchors against material hashes the inventory did not "
            f"record: {drifted}. The anchor id matched but the bytes behind it did "
            f"not, so the citation points at content nobody read."
        )


def _closure_evidence(artifact: LabCairnModel, upstream: Upstream) -> None:
    ledger = artifact
    if not isinstance(ledger, EvidenceLedgerView):
        raise DerivationClosureError(f"expected EvidenceLedgerView, got {type(ledger).__name__}")
    retrieved = upstream.expect(RetrievedExcerpts)
    assert isinstance(retrieved, RetrievedExcerpts)
    allowed = retrieved.excerpt_index()
    for claim in ledger.claims:
        unknown = sorted({ref.anchor_id for ref in claim.anchor_refs} - set(allowed))
        if unknown:
            raise DerivationClosureError(
                f"claim {claim.claim_id!r} cites anchors {unknown} that retrieval did "
                f"not return. Retrievable anchors: {sorted(allowed)}."
            )
        drifted = sorted(
            f"{ref.anchor_id} (claim says {ref.material_sha256!r}, retrieval says "
            f"{allowed[ref.anchor_id]!r})"
            for ref in claim.anchor_refs
            if allowed.get(ref.anchor_id) != ref.material_sha256
        )
        if drifted:
            raise DerivationClosureError(
                f"claim {claim.claim_id!r} cites anchors against material hashes that "
                f"differ from what retrieval recorded: {drifted}."
            )


def _closure_propose(artifact: LabCairnModel, upstream: Upstream) -> None:
    proposal = artifact
    if not isinstance(proposal, ResearchProposal):
        raise DerivationClosureError(f"expected ResearchProposal, got {type(proposal).__name__}")
    ledger = upstream.expect(EvidenceLedgerView)
    assert isinstance(ledger, EvidenceLedgerView)
    known = ledger.claim_ids()
    for item in proposal.items:
        _require_subset(item.evidence_refs, known, "claim id", f"proposal item {item.item_id!r}")
        if item.materiality.requires_approval and not item.evidence_refs:
            raise DerivationClosureError(
                f"proposal item {item.item_id!r} is {item.materiality.value!r} and cites "
                f"no claim. A direction change the ledger cannot be shown to rest on "
                f"is exactly the kind that has to go to a human before any work "
                f"follows it."
            )


def _closure_draft(artifact: LabCairnModel, upstream: Upstream) -> None:
    draft = artifact
    if not isinstance(draft, ReportDraft):
        raise DerivationClosureError(f"expected ReportDraft, got {type(draft).__name__}")
    ledger = upstream.expect(EvidenceLedgerView)
    assert isinstance(ledger, EvidenceLedgerView)
    known = ledger.claim_ids()
    for section in draft.sections:
        _require_subset(
            section.evidence_refs, known, "claim id", f"draft section {section.section_id!r}"
        )


def _closure_validate(artifact: LabCairnModel, upstream: Upstream) -> None:
    report = artifact
    if not isinstance(report, ValidationReport):
        raise DerivationClosureError(f"expected ValidationReport, got {type(report).__name__}")
    draft = upstream.expect(ReportDraft)
    assert isinstance(draft, ReportDraft)
    expected = set(draft.section_ids())
    _require_subset(report.checked_sections, tuple(expected), "draft section", "validation report")
    missing = sorted(expected - set(report.checked_sections))
    if missing:
        raise DerivationClosureError(
            f"validation passed {sorted(report.checked_sections)} and never looked at "
            f"{missing}. A verdict is about the artifact it checked; one that skips "
            f"sections says nothing about the report."
        )
    _require_subset(
        tuple(f.target_section_id for f in report.findings),
        tuple(expected),
        "draft section",
        "validation finding",
    )


def _closure_deliver(artifact: LabCairnModel, upstream: Upstream) -> None:
    delivery = artifact
    if not isinstance(delivery, DeliveredReport):
        raise DerivationClosureError(f"expected DeliveredReport, got {type(delivery).__name__}")
    draft_entry = upstream.entry(ArtifactKind.REPORT_DRAFT)
    validation_entry = upstream.entry(ArtifactKind.VALIDATION_REPORT)
    assert isinstance(draft_entry.artifact, ReportDraft)
    assert isinstance(validation_entry.artifact, ValidationReport)
    if delivery.draft_digest != draft_entry.digest:
        raise DerivationClosureError(
            f"delivered report names draft digest {delivery.draft_digest!r} but this "
            f"run's draft hashed to {draft_entry.digest!r}. The deliverable is about a "
            f"different draft than the one that was validated."
        )
    if delivery.validation_verdict is not validation_entry.artifact.verdict:
        raise DerivationClosureError(
            f"delivered report restates the verdict as "
            f"{delivery.validation_verdict.value!r} while validation returned "
            f"{validation_entry.artifact.verdict.value!r}. A deliverable may not "
            f"report a more favourable verdict than the validation reached."
        )


#: Per-stage reference-closure rules, keyed by the stage whose *output* is being
#: checked. ``intake`` is absent because it reads nothing, and ``intake`` being
#: absent is a fact rather than an oversight — the table is asserted complete
#: against the stage list elsewhere.
CLOSURE_RULES: Final[dict[StageName, ClosureRule]] = {
    StageName.INVENTORY: _closure_inventory,
    StageName.RETRIEVE: _closure_retrieve,
    StageName.EVIDENCE: _closure_evidence,
    StageName.PROPOSE: _closure_propose,
    StageName.DRAFT: _closure_draft,
    StageName.VALIDATE: _closure_validate,
    StageName.DELIVER: _closure_deliver,
}


def require_closure(stage: StageName, artifact: LabCairnModel, upstream: Upstream) -> None:
    """Apply *stage*'s closure rule to *artifact* given what it was built from.

    :raises DerivationClosureError: naming the ids or hashes that do not resolve,
        because "closure failed" is not something an operator can act on.
    """
    rule = CLOSURE_RULES.get(stage)
    if rule is not None:
        rule(artifact, upstream)


__all__ = [
    "BODY_FIELDS",
    "CLOSURE_RULES",
    "CONTRACT_MODELS",
    "FORMAT_FIELDS",
    "IDENTIFIER_FIELDS",
    "MIN_SUBSTANTIVE_CHARS",
    "PLACEHOLDER_TOKENS",
    "PRIMARY_CONTENT_FIELDS",
    "PROSE_FIELDS",
    "ClosureRule",
    "Upstream",
    "UpstreamArtifact",
    "is_placeholder_token",
    "iter_text_fields",
    "normalize_placeholder_text",
    "require_closure",
    "require_substance",
    "string_field_names",
    "substantive_length",
]
