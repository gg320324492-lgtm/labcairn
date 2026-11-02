"""The run driver for LC-P2-14's blind evaluation: five arms, cases, sheets, verdicts.

**What this module is for.** The protocol's machinery (``arms.py``,
``split_check.py``, ``blind_sheet.py``, ``significance.py``) can say whether a
*configuration* is runnable, whether a split leaks, whether a sheet is blind
and whether a contrast is significant. It cannot run anything. This module is
the missing middle: it takes the five arms and a case set, asks a provider for
one output per arm-and-case, writes the artefacts a rater can read, and then
walks the same pipeline the protocol describes — blind sheet, two raters and an
arbiter, unblinding, the two contrasts, the report.

**Two modes, and the difference between them is the point.**

* **Dry run.** A stub provider answers every request. It is not a model: it
  records that it was asked and returns a deterministic sentence that says no
  model was involved. The ratings it writes are the protocol's ``unknown``
  label on every dimension — *the evidence does not settle this* — because a
  dry run has no evidence to settle anything with. So the run exercises every
  wire in the machine and **claims nothing**: ``model`` is empty,
  ``provider_calls`` is zero, the significance verdicts are the not-significant
  path by rule, and the report says so in its own words.
* **Real.** The only provider this driver constructs is
  :class:`~labcairn.providers.adapter.PydanticAiModelProvider`, and it cannot
  be built without an :class:`~labcairn.providers.consent.OutboundConsent` and
  a :class:`~labcairn.providers.budget.RunBudget` with at least one ceiling.
  The driver therefore **refuses before constructing anything** when either is
  absent, naming what the owner has to bring. It does not have a second path
  around the outbound bridge, and it does not invent an approval.

**A real run stops at AWAITING RATINGS.** Two independent raters and an
arbiter are people. The driver writes the blind packet and the run record,
reports ``significance: NOT RUN`` as a first-class status, and leaves the
numbers alone until :func:`run_score` is handed real sheets.

**Why item ids are hashes.** The blind packet must not name an arm, and an
item id that spells ``arm-A-case-01`` names one to anyone who reads it. So the
id is a digest of arm and case, and the mapping lives in ``unblinding.json`` —
the file a rater does not receive.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from labcairn.application.approvals import ApprovalUse
from labcairn.application.context import ApplicationContext
from labcairn.application.outbound import OutboundApproval
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.protocol import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    UsageReport,
)
from labcairn.core.providers.usage import Unknown, UnknownReason
from labcairn.providers.adapter import PydanticAiModelProvider, prompt_digest
from labcairn.providers.budget import RunBudget
from labcairn.providers.consent import OutboundConsent
from labcairn.providers.credentials import ProviderSettings
from labcairn.providers.errors import OutboundRefusedError
from labcairn.providers.pydantic_models import build_model
from labcairn.providers.usage_capture import UsageCapture

from . import blind_sheet, significance, split_check
from .arms import ARM_IDS, EXPECTED_INPUTS, INPUT_FACES, ArmConfiguration, assess_configuration
from .blind_sheet import ExcludedRating, ResolvedRating

#: The mode labels a run record carries.
MODE_DRY_RUN: Final = "dry-run"
MODE_REAL: Final = "real"
MODE_SCORE: Final = "score"

#: The statuses a run record carries. ``awaiting-ratings`` is a first-class
#: state: a real run that has produced artefacts and stopped is not a failed
#: run, and it is not an evaluated one either.
STATUS_DRY_RUN_COMPLETE: Final = "dry-run-complete"
STATUS_AWAITING_RATINGS: Final = "awaiting-ratings"
STATUS_EVALUATED: Final = "evaluated"
STATUS_REFUSED: Final = "refused"

#: The model string a dry run declares. The report's ``model`` field is the
#: empty string, matching LC-P2-00's baseline; the arms still need a non-empty
#: declaration to pass :func:`assess_configuration`, so the configuration says
#: plainly that it is unbound.
DRY_RUN_MODEL: Final = "unbound (dry run: no provider)"
DRY_RUN_BUDGET: Final = "dry run: no provider calls, so no provider budget"

#: The provider name a dry run records. It is deliberately not a model name.
DRY_RUN_PROVIDER: Final = "dry-run-stub"

#: The two raters a dry run writes. Their names say what they are, so a sheet
#: that escapes this directory cannot be mistaken for a human rating.
DRY_RUN_RATER_A: Final = "dry-run-synthetic-rater-a"
DRY_RUN_RATER_B: Final = "dry-run-synthetic-rater-b"

#: The number of synthetic cases the dry run uses. It matches the protocol's
#: planned case set; it is a fixture count, not a measured denominator.
DRY_RUN_CASE_COUNT: Final = 16

#: The contrats the protocol says matter. Imported from ``arms`` would be
#: better, but the pair names here are the report's own labels.
CONTRASTS: Final[tuple[tuple[str, str, str], ...]] = (
    ("D vs C", "D", "C"),
    ("E vs D", "E", "D"),
)

#: The fixed timestamp a dry-run response carries. The epoch is not a
#: measurement; it says "this response was not observed at a real moment".
_DRY_RUN_OBSERVED_AT: Final = datetime(1970, 1, 1, tzinfo=UTC)

#: The evidence faces whose material is a version of the paper. The split
#: checker distinguishes these from rules and assessments.
_VERSION_FACES: Final = frozenset({"draft", "version_differences"})


class RunRefusedError(RuntimeError):
    """The driver refused to run, and the message says what is missing."""


class RealRunRefusedError(RunRefusedError):
    """A real run was asked for without what the outbound bridge requires."""


@dataclass(frozen=True, slots=True)
class CaseSpec:
    """One evaluation case: the question and the material each arm may see.

    ``evidence`` is keyed by the protocol's closed face vocabulary. Every face
    is required, because the five arms each take a different subset and a case
    missing a face would make one arm's prompt silently shorter than another's
    — which is a difference between the arms that the protocol did not declare.
    """

    case_id: str
    paper_id: str
    question: str
    evidence: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("a case needs an id")
        if not self.paper_id.strip():
            raise ValueError(f"case {self.case_id} names no paper")
        if not self.question.strip():
            raise ValueError(f"case {self.case_id} asks no question")
        unknown = sorted(set(self.evidence) - set(INPUT_FACES))
        if unknown:
            raise ValueError(
                f"case {self.case_id} carries evidence faces the protocol does "
                f"not name: {', '.join(unknown)}"
            )
        absent = sorted(set(INPUT_FACES) - set(self.evidence))
        if absent:
            raise ValueError(
                f"case {self.case_id} is missing evidence for "
                f"{', '.join(absent)}; every arm's prompt is built from these "
                "faces, and a missing one would shorten one arm silently"
            )

    def to_document(self) -> dict[str, Any]:
        """The case as a JSON-ready document."""
        return {
            "case_id": self.case_id,
            "paper_id": self.paper_id,
            "question": self.question,
            "evidence": dict(sorted(self.evidence.items())),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> CaseSpec:
        """Read one case, refusing a document that is not complete."""
        for field_name in ("case_id", "paper_id", "question", "evidence"):
            if field_name not in document:
                raise ValueError(f"a case document carries no {field_name}")
        evidence = document["evidence"]
        if not isinstance(evidence, Mapping):
            raise ValueError("a case's evidence is not an object")
        return cls(
            case_id=str(document["case_id"]),
            paper_id=str(document["paper_id"]),
            question=str(document["question"]),
            evidence={str(face): str(text) for face, text in evidence.items()},
        )


@dataclass(frozen=True, slots=True)
class CaseSet:
    """The cases one run evaluates, refused unless they are a usable set."""

    cases: tuple[CaseSpec, ...]

    def __post_init__(self) -> None:
        if not self.cases:
            raise ValueError("a run needs at least one case")
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("two cases share one case_id")
        # Two cases of one paper are allowed, and the protocol expects them:
        # the split's unit is the paper, so several cases may sit on one paper
        # as long as every one of them sits on the same side. The split check
        # is what holds that, not this constructor.

    @property
    def case_ids(self) -> tuple[str, ...]:
        """The ids, in the order the set holds them."""
        return tuple(case.case_id for case in self.cases)

    def to_document(self) -> dict[str, Any]:
        """The set as a JSON-ready document."""
        return {"cases": [case.to_document() for case in self.cases]}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> CaseSet:
        """Read a case set from a JSON document."""
        raw = document.get("cases")
        if not isinstance(raw, list) or not raw:
            raise ValueError("a case set document carries no cases")
        return cls(tuple(CaseSpec.from_document(one) for one in raw if isinstance(one, Mapping)))


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """One arm's answer to one case, with the provenance a reader needs."""

    item_id: str
    case_id: str
    arm_id: str
    prompt_digest: str
    output: str
    provider: str
    usage: Mapping[str, object]

    def to_document(self) -> dict[str, Any]:
        """The artefact as a JSON-ready document."""
        return {
            "item_id": self.item_id,
            "case_id": self.case_id,
            "arm_id": self.arm_id,
            "prompt_digest": self.prompt_digest,
            "output": self.output,
            "provider": self.provider,
            "usage": dict(self.usage),
        }


@dataclass(frozen=True, slots=True)
class RunSummary:
    """What one run produced, in the shape a caller and the report both read."""

    mode: str
    status: str
    out_dir: Path
    artifacts: tuple[ArtifactRecord, ...]
    provider_calls: int
    stub_calls: int
    model: str
    budget: str
    cases: tuple[str, ...]
    arms: tuple[str, ...]
    split_clean: bool
    contrasts: tuple[significance.ContrastReport, ...]
    ratings: Mapping[str, Any]
    refusal: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    """One owner approval, paired with the use it was granted for.

    The driver never decides the use: it reads it from the owner's approval
    record and hands the pair to the application layer's
    :class:`~labcairn.application.outbound.OutboundApproval`, which re-checks
    the digest against the ledger.
    """

    approval_id: UUID
    use: ApprovalUse


class ConsumingApprovals:
    """The consent port a real run hands the provider: one approval per request.

    The provider calls :meth:`require` once per request, and this object passes
    that request to the application layer's own
    :class:`~labcairn.application.outbound.OutboundApproval`, which spends the
    approval through :func:`~labcairn.application.approvals.consume_approval`.
    **No consent logic is re-implemented here**: this object only chooses which
    granted approval to hand over next, and refuses when the owner supplied
    fewer approvals than the run has requests.

    The queue is empty-checked here rather than by the provider, because the
    provider's refusal is a per-request refusal and the run should stop with a
    message about the missing approvals.
    """

    def __init__(
        self,
        context: ApplicationContext,
        grants: Sequence[ApprovalGrant],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not grants:
            raise RealRunRefusedError(
                "a real run needs at least one owner approval; none was supplied"
            )
        self._context = context
        self._pending = list(grants)
        self._clock = clock if clock is not None else _utc_now
        self._spent = 0

    @property
    def remaining(self) -> int:
        """How many approvals the run has left to spend."""
        return len(self._pending)

    @property
    def spent(self) -> int:
        """How many approvals the run has spent."""
        return self._spent

    def require(self, request: ModelRequest) -> None:
        """Spend the next approval on this request, or refuse the transmission."""
        if not self._pending:
            raise OutboundRefusedError(
                "the run has no owner approval left for this request; the "
                "provider refuses the transmission rather than sending it"
            )
        grant = self._pending.pop(0)
        OutboundApproval(
            self._context,
            ApprovalId(grant.approval_id),
            grant.use,
            self._clock(),
        ).require(request)
        self._spent += 1


def _utc_now() -> datetime:
    """The wall clock, used only by a real run's approval consumption.

    A dry run never reaches this function; it is a named seam so a test can
    pass a frozen clock and the run stays replayable.
    """
    return datetime.now(UTC)


class DryRunProvider:
    """The stub a dry run sends to: it records the request and invents no result.

    It is deliberately **not** :class:`~labcairn.core.providers.fake.FakeProvider`.
    The fake replays a scripted transcript, which is the right device for a
    test that knows the exact request; a dry run's requests are built from
    arms and cases, and what the driver needs to prove is that the calls happen
    on a stub and not on a provider. So this stub answers every request with a
    sentence that names the prompt digest and says no model was called, and
    records every request it saw.

    ``provider_calls`` in the run record counts calls that left the process;
    this stub increments ``stub_calls`` instead, so the two numbers stay
    separately readable.
    """

    def __init__(self) -> None:
        self._calls: list[ModelRequest] = []

    @property
    def name(self) -> str:
        """The stable, non-secret identifier the run record carries."""
        return DRY_RUN_PROVIDER

    @property
    def calls(self) -> tuple[ModelRequest, ...]:
        """Every request this stub was asked, in order."""
        return tuple(self._calls)

    def send(self, request: ModelRequest) -> ModelResponse:
        """Record the request and return a deterministic non-answer."""
        self._calls.append(request)
        digest = prompt_digest(request.prompt)
        return ModelResponse(
            text=(f"[dry-run synthetic output] no model was called. prompt digest: {digest[:16]}"),
            tool_calls=(),
            usage=UsageReport(
                input_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
                output_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
            ),
            observed_at=_DRY_RUN_OBSERVED_AT,
            transcript_step=f"dry-run-{len(self._calls):03d}",
        )


def default_arms(*, model: str, budget: str) -> tuple[ArmConfiguration, ...]:
    """The protocol's five arms, each declaring exactly the inputs its letter names."""
    return tuple(
        ArmConfiguration(
            arm_id=letter,
            model=model,
            budget=budget,
            inputs=EXPECTED_INPUTS[letter],
        )
        for letter in ARM_IDS
    )


def item_id_for(arm_id: str, case_id: str) -> str:
    """The anonymous id of one arm's answer to one case.

    A digest, not a spelling: an id that says ``A`` would break the blind
    sheet's anonymity before a rater opened it. The mapping is written to
    ``unblinding.json`` and is not part of the blind packet.
    """
    material = f"labcairn.blind.item.v1\x00{arm_id}\x00{case_id}".encode()
    return "item-" + hashlib.sha256(material).hexdigest()[:16]


def render_prompt(case: CaseSpec, arm: ArmConfiguration) -> str:
    """Build one arm's prompt from exactly the evidence faces it declares.

    The prompt deliberately carries **no arm id**. A model told which arm it is
    in is a model that can behave differently because of the label, and the
    protocol's comparison is between evidence sets, not between labels.

    The face order is :data:`~tests.evaluation.arms.INPUT_FACES`'s order, not
    the arm's set order, so two arms that share a face present it at the same
    position. That is a small thing that makes the prompts comparable as text
    as well as as configurations.
    """
    missing = sorted(face for face in arm.inputs if face not in case.evidence)
    if missing:
        raise RunRefusedError(
            f"arm {arm.arm_id} declares evidence faces case {case.case_id} does "
            f"not carry: {', '.join(missing)}"
        )
    sections = [
        "# LC-P2-14 evaluation case",
        "",
        f"case_id: {case.case_id}",
        f"question: {case.question}",
        "",
        "Answer the question using only the material below.",
        "",
    ]
    for face in INPUT_FACES:
        if face not in arm.inputs:
            continue
        sections.extend([f"## {face}", "", case.evidence[face].strip(), ""])
    return "\n".join(sections).rstrip() + "\n"


def synthetic_cases() -> tuple[CaseSpec, ...]:
    """Sixteen synthetic cases, each labelled as a fixture in its own material.

    These are **not** unseen papers. They are a deterministic case set that
    lets the dry run exercise the whole pipeline without pretending a real
    paper was read, and every evidence text says ``[synthetic fixture]`` so a
    packet that escapes its directory cannot be mistaken for a real one.
    """
    cases: list[CaseSpec] = []
    for number in range(1, DRY_RUN_CASE_COUNT + 1):
        case_id = f"case-{number:02d}"
        paper_id = f"synthetic-paper-{number:02d}"
        question = (
            f"[synthetic fixture] What does the current draft claim about "
            f"finding {number}, and does the cited evidence support it?"
        )
        evidence = {
            "draft": (
                f"[synthetic fixture] Draft {number}: the text claims that the "
                "observed effect is supported by the cited table, without "
                "stating the uncertainty."
            ),
            "literature": (
                f"[synthetic fixture] Two related reports for finding {number}: "
                "one reports the same direction, one reports a smaller effect."
            ),
            "version_differences": (
                f"[synthetic fixture] Version difference {number}: the earlier "
                "draft reported the effect without the unit, and the current "
                "draft adds the unit but not the interval."
            ),
            "advisor_comments": (
                f"[synthetic fixture] Advisor comment {number}: state what the "
                "table measures before interpreting the difference."
            ),
            "student_responses": (
                f"[synthetic fixture] Student response {number}: the table "
                "measures the difference between the two conditions."
            ),
            "review_outcome": (
                f"[synthetic fixture] Review outcome {number}: the reviewer "
                "asked for the uncertainty to be reported with the effect."
            ),
            "confirmed_rules": (
                f"[synthetic fixture] Confirmed rule {number}: when a claim "
                "rests on a numeric table, name the quantity and its unit."
            ),
        }
        cases.append(
            CaseSpec(
                case_id=case_id,
                paper_id=paper_id,
                question=question,
                evidence=evidence,
            )
        )
    return tuple(cases)


def _check_configuration(arms: Sequence[ArmConfiguration]) -> None:
    """Refuse a set of arms the protocol's own configuration check refuses."""
    outcome = assess_configuration(tuple(arms))
    if not outcome.admissible:
        raise RunRefusedError(
            "the arm configuration cannot be run: " + "; ".join(outcome.violations)
        )


def _check_split(cases: Sequence[CaseSpec]) -> split_check.LeakReport:
    """Run the protocol's leak check over the case set's own material.

    Every case and every piece of its material sits on the evaluation side
    here: a dry run has no development side, and inventing one would be a
    split the checker could not honestly call clean. What this proves is that
    the *shape* the driver feeds the checker is the shape the checker reads —
    and a real case set is checked by the same call.
    """
    assignments = {case.paper_id: split_check.EVALUATION for case in cases}
    entries: list[split_check.CorpusEntry] = []
    for case in cases:
        for face in INPUT_FACES:
            kind = (
                split_check.KIND_VERSION if face in _VERSION_FACES else split_check.KIND_ASSESSMENT
            )
            entries.append(
                split_check.CorpusEntry(
                    paper_id=case.paper_id,
                    kind=kind,
                    side=split_check.EVALUATION,
                    version_id="v1" if face in _VERSION_FACES else "",
                )
            )
    return split_check.check_split(assignments, entries)


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    """Write one JSON document deterministically."""
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    """Write one text document."""
    path.write_text(text, encoding="utf-8")


def _usage_document(response: ModelResponse) -> dict[str, object]:
    """The usage block as JSON-ready data."""
    return dict(response.usage.to_wire())


def _record_artifacts(
    provider: ModelProvider,
    arms: Sequence[ArmConfiguration],
    cases: Sequence[CaseSpec],
    *,
    on_each: Callable[[ArtifactRecord], None] | None = None,
) -> tuple[tuple[ArtifactRecord, ...], int]:
    """Send one request per arm and case, and return what came back.

    The return value's second item counts calls on the provider. The dry run
    passes a :class:`DryRunProvider` and reports that count as ``stub_calls``;
    a real run passes :class:`~labcairn.providers.adapter.PydanticAiModelProvider`
    and reports it as ``provider_calls``. The two are never added together.

    ``on_each`` is called once per completed artifact. A real run uses it to
    keep the answers that were already paid for when a later request is
    refused; a refused run that reported zero calls after sending thirty
    would be a record that hides money it spent.
    """
    artifacts: list[ArtifactRecord] = []
    calls = 0
    for arm in arms:
        for case in cases:
            prompt = render_prompt(case, arm)
            response = provider.send(ModelRequest(prompt=prompt))
            calls += 1
            artifact = ArtifactRecord(
                item_id=item_id_for(arm.arm_id, case.case_id),
                case_id=case.case_id,
                arm_id=arm.arm_id,
                prompt_digest=prompt_digest(prompt),
                output=response.text,
                provider=provider.name,
                usage=_usage_document(response),
            )
            artifacts.append(artifact)
            if on_each is not None:
                on_each(artifact)
    return tuple(artifacts), calls


def _write_artifacts(out_dir: Path, artifacts: Sequence[ArtifactRecord]) -> None:
    """Write one JSON file per artefact, named by its anonymous item id."""
    directory = out_dir / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        _write_json(directory / f"{artifact.item_id}.json", artifact.to_document())


def _write_blind_packet(
    out_dir: Path,
    artifacts: Sequence[ArtifactRecord],
    cases: Sequence[CaseSpec],
) -> None:
    """Write what a rater receives: anonymous items, outputs and the question.

    ``case_id`` is present because a rater has to know which case an answer
    belongs to; it is not an arm. The output text carries no arm either — the
    dry-run stub makes sure of that, and a real run's prompt carries no arm id.
    """
    by_case = {case.case_id: case for case in cases}
    items = [
        {
            "item_id": artifact.item_id,
            "case_id": artifact.case_id,
            "question": by_case[artifact.case_id].question,
            "output": artifact.output,
        }
        for artifact in artifacts
    ]
    _write_json(
        out_dir / "blind_packet.json",
        {
            "sheet_id": "lc-p2-14-blind-packet",
            "instructions": (
                "Rate each item on the five protocol dimensions with yes, no "
                "or unknown. Do not infer the arm: the packet does not carry "
                "it, and the mapping is withheld until both sheets are in."
            ),
            "items": items,
        },
    )


def _write_unblinding(
    out_dir: Path,
    artifacts: Sequence[ArtifactRecord],
) -> None:
    """Write the item-to-arm and item-to-case mapping, for scoring only."""
    _write_json(
        out_dir / "unblinding.json",
        {
            "items": {
                artifact.item_id: {
                    "arm": artifact.arm_id,
                    "case": artifact.case_id,
                }
                for artifact in artifacts
            },
            "notice": (
                "This file is the unblinding act. It is not part of the blind "
                "packet and must not be given to a rater."
            ),
        },
    )


def load_unblinding(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Read an unblinding map, refusing a document that is not complete."""
    document = json.loads(path.read_text(encoding="utf-8"))
    items = document.get("items")
    if not isinstance(items, Mapping):
        raise ValueError("the unblinding document carries no items")
    item_arms: dict[str, str] = {}
    item_cases: dict[str, str] = {}
    for item_id, entry in items.items():
        if not isinstance(entry, Mapping) or "arm" not in entry or "case" not in entry:
            raise ValueError(f"unblinding entry {item_id} carries no arm or case")
        item_arms[str(item_id)] = str(entry["arm"])
        item_cases[str(item_id)] = str(entry["case"])
    return item_arms, item_cases


def _synthetic_rating_document(
    sheet_id: str,
    rater: str,
    item_ids: Sequence[str],
) -> dict[str, Any]:
    """A dry-run rater's sheet: every dimension ``unknown``, on every item.

    ``unknown`` is the protocol's label for *the evidence does not settle
    this*. A dry run has no evidence, so it is the only label this driver may
    write without inventing a judgement. The consequence is visible in the
    report: every contrast is a tie and every verdict is not significant.
    """
    return {
        "sheet_id": sheet_id,
        "rater": rater,
        "items": [
            {
                "item_id": item_id,
                "ratings": dict.fromkeys(blind_sheet.DIMENSIONS, blind_sheet.LABEL_UNKNOWN),
            }
            for item_id in item_ids
        ],
    }


def _arbiter_document() -> dict[str, Any]:
    """An empty arbiter record, for sheets that agree by construction."""
    return {"arbitrations": []}


def _load_arbiter(path: Path | None) -> dict[tuple[str, str], str]:
    """Read the arbiter's decisions, or an empty mapping when there is no file."""
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    raw = document.get("arbitrations", [])
    if not isinstance(raw, list):
        raise ValueError("the arbiter document's arbitrations are not a list")
    decisions: dict[tuple[str, str], str] = {}
    for one in raw:
        if not isinstance(one, Mapping):
            raise ValueError("an arbitration is not an object")
        for field_name in ("item_id", "dimension", "label"):
            if field_name not in one:
                raise ValueError(f"an arbitration carries no {field_name}")
        label = str(one["label"])
        if label not in blind_sheet.RATING_LABELS:
            raise ValueError(f"an arbitration carries an unknown label {label!r}")
        decisions[(str(one["item_id"]), str(one["dimension"]))] = label
    return decisions


def _resolve(
    sheets: tuple[blind_sheet.BlindSheet, blind_sheet.BlindSheet],
    arbiter: Mapping[tuple[str, str], str],
) -> tuple[tuple[ResolvedRating, ...], tuple[ExcludedRating, ...]]:
    """Settle the two sheets into one label per item and dimension."""
    return blind_sheet.resolve_pair(sheets[0], sheets[1], arbiter)


def _build_contrasts(
    resolved: Sequence[ResolvedRating],
    excluded: Sequence[ExcludedRating],
    item_arms: Mapping[str, str],
    item_cases: Mapping[str, str],
) -> tuple[significance.ContrastReport, ...]:
    """Build both contrasts, each over all five dimensions."""
    reports: list[significance.ContrastReport] = []
    for label, treatment, control in CONTRASTS:
        reports.append(
            significance.build_report(
                label,
                resolved,
                excluded,
                item_arms,
                item_cases,
                treatment,
                control,
            )
        )
    return tuple(reports)


def _ratings_summary(
    resolved: Sequence[ResolvedRating],
    excluded: Sequence[ExcludedRating],
    *,
    synthetic: bool,
) -> dict[str, Any]:
    """The rating resolution's own denominators, as the report states them."""
    return {
        "synthetic": synthetic,
        "raters": 2,
        "resolved": len(resolved),
        "excluded": len(excluded),
        "excluded_rating": [
            {"item_id": rating.item_id, "dimension": rating.dimension, "reason": rating.reason}
            for rating in excluded
        ],
        "reason": (
            "the dry run wrote the protocol's unknown label on every dimension: "
            "no evidence was read, so no verdict was invented"
            if synthetic
            else "two independent raters and an arbiter"
        ),
    }


def _contrasts_document(
    reports: Sequence[significance.ContrastReport],
    *,
    synthetic: bool,
) -> dict[str, Any]:
    """Both contrast reports as JSON-ready data, with their honesty label."""
    return {
        "synthetic": synthetic,
        "contrasts": [
            {
                "contrast": report.contrast,
                "rows": [
                    {
                        "dimension": row.dimension,
                        "wins": row.verdict.counts.wins,
                        "losses": row.verdict.counts.losses,
                        "ties": row.verdict.counts.ties,
                        "cases": row.verdict.counts.cases,
                        "significant": row.verdict.significant,
                        "p_value": row.verdict.p_value,
                        "difference": row.verdict.difference,
                        "agreed": row.agreed,
                        "arbitrated": row.arbitrated,
                        "excluded": row.excluded,
                        "reason": row.verdict.reason,
                    }
                    for row in report.rows
                ],
            }
            for report in reports
        ],
    }


def _render_report(
    *,
    mode: str,
    status: str,
    model: str,
    budget: str,
    provider_calls: int,
    stub_calls: int,
    cases: Sequence[str],
    arms: Sequence[str],
    split_clean: bool,
    reports: Sequence[significance.ContrastReport],
    ratings: Mapping[str, Any],
) -> str:
    """The human-readable report, with its honesty label at the top."""
    lines = [
        "# LC-P2-14 — blind evaluation run",
        "",
        f"**Mode:** `{mode}` · **Status:** `{status}`",
        "",
    ]
    if mode == MODE_DRY_RUN:
        lines.extend(
            [
                "> **DRY RUN — nothing here is a measurement of a model.**",
                "> No model was contacted. The provider calls below happened on a",
                "> stub that records requests and returns a sentence saying so.",
                "> Every rating is the protocol's `unknown` label, because a dry",
                "> run has no evidence to settle a rating with. The significance",
                "> rows are therefore the not-significant path by rule, and they",
                "> say nothing about any arm's capability.",
                "",
            ]
        )
    elif status == STATUS_AWAITING_RATINGS:
        lines.extend(
            [
                "> **AWAITING RATINGS — significance was not computed.**",
                "> The artefacts and the blind packet are complete. The protocol",
                "> needs two independent raters and an arbiter; until their",
                "> sheets arrive, this run claims no comparison.",
                "",
            ]
        )
    lines.extend(
        [
            "## The run",
            "",
            f"- model: `{model or '(none declared)'}`",
            f"- budget: `{budget}`",
            f"- cases: {len(cases)}",
            f"- arms: {', '.join(arms)}",
            f"- provider calls: {provider_calls}",
            f"- stub calls: {stub_calls}",
            f"- split check: {'clean' if split_clean else 'LEAKS FOUND'}",
            "",
        ]
    )
    if ratings:
        lines.extend(
            [
                "## Ratings",
                "",
                f"- synthetic: {ratings.get('synthetic')}",
                f"- resolved labels: {ratings.get('resolved')}",
                f"- excluded: {ratings.get('excluded')}",
                "",
            ]
        )
    if reports:
        lines.extend(["## The two contrasts", ""])
        for report in reports:
            lines.append(f"### {report.contrast}")
            lines.append("")
            lines.append("| dimension | wins | losses | ties | cases | significant | p |")
            lines.append("|---|---|---|---|---|---|---|")
            for row in report.rows:
                verdict = row.verdict
                p_value = "—" if verdict.p_value is None else f"{verdict.p_value:.4f}"
                lines.append(
                    f"| {row.dimension} | {verdict.counts.wins} | "
                    f"{verdict.counts.losses} | {verdict.counts.ties} | "
                    f"{verdict.counts.cases} | {verdict.significant} | {p_value} |"
                )
            lines.append("")
            lines.append("A significant difference in one dimension is not a phase gate.")
            lines.append("")
    else:
        lines.extend(
            [
                "## The two contrasts",
                "",
                "**NOT RUN.** The protocol requires two independent raters and an",
                "arbiter, and no rating sheets have been scored. This is an",
                "honest status, not a zero and not a failed comparison.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _run_record(
    *,
    mode: str,
    status: str,
    model: str,
    budget: str,
    provider_calls: int,
    stub_calls: int,
    cases: Sequence[str],
    arms: Sequence[ArmConfiguration],
    split_clean: bool,
    reports: Sequence[significance.ContrastReport],
    ratings: Mapping[str, Any],
    synthetic: bool,
    refusal: str | None = None,
) -> dict[str, Any]:
    """The machine-readable run record."""
    record: dict[str, Any] = {
        "work_order": "LC-P2-14",
        "mode": mode,
        "status": status,
        "model": model,
        "budget": budget,
        "provider_calls": provider_calls,
        "stub_calls": stub_calls,
        "cases": list(cases),
        "arms": [arm.to_document() for arm in arms],
        "split": {"clean": split_clean},
        "ratings": dict(ratings),
        "significance": (
            _contrasts_document(reports, synthetic=synthetic)
            if reports
            else {
                "status": "NOT RUN",
                "reason": (
                    "the protocol requires two independent raters and an "
                    "arbiter; no scored sheets are present"
                ),
            }
        ),
        "limitations": (
            "the dry run used a stub that is not a model; every rating is the "
            "protocol's unknown label; the numbers are not a measurement of any "
            "arm's capability"
            if synthetic
            else (
                "a real run measures the provider's outputs only after two "
                "independent raters and an arbiter have scored them; until then "
                "no comparison is claimed"
            )
        ),
    }
    if refusal is not None:
        record["refusal"] = refusal
    return record


def run_dry(
    *,
    out_dir: Path,
    cases: Sequence[CaseSpec] | None = None,
    arms: Sequence[ArmConfiguration] | None = None,
) -> RunSummary:
    """Run the whole pipeline against a stub, and claim nothing.

    The steps, in order: check the arm configuration; check the split; send
    one request per arm and case to :class:`DryRunProvider`; write artefacts
    and the blind packet; write two synthetic sheets (every dimension
    ``unknown``); load them through the real loader; unblind through the real
    unblinding map; build both contrasts; write the report.

    Every step uses the production modules, so a dry run that completes is
    evidence that the wiring is complete. It is **not** evidence about a
    model, and the record says so in ``model``, ``provider_calls`` and
    ``limitations``.
    """
    arms = tuple(
        arms if arms is not None else default_arms(model=DRY_RUN_MODEL, budget=DRY_RUN_BUDGET)
    )
    case_set = CaseSet(tuple(cases) if cases is not None else synthetic_cases())
    _check_configuration(arms)
    leak_report = _check_split(case_set.cases)
    if not leak_report.clean:
        raise RunRefusedError(
            "the split leaks, so nothing is run: "
            + "; ".join(f"{leak.shape}: {leak.detail}" for leak in leak_report.leaks)
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    provider = DryRunProvider()
    artifacts, stub_calls = _record_artifacts(provider, arms, case_set.cases)
    _write_artifacts(out_dir, artifacts)
    _write_blind_packet(out_dir, artifacts, case_set.cases)
    _write_unblinding(out_dir, artifacts)

    expected_item_ids = [artifact.item_id for artifact in artifacts]
    sheets = (
        blind_sheet.load_blind_sheet(
            _synthetic_rating_document("dry-run-sheet-a", DRY_RUN_RATER_A, expected_item_ids),
            expected_item_ids,
        ),
        blind_sheet.load_blind_sheet(
            _synthetic_rating_document("dry-run-sheet-b", DRY_RUN_RATER_B, expected_item_ids),
            expected_item_ids,
        ),
    )
    ratings_dir = out_dir / "ratings"
    ratings_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        ratings_dir / "rater-a.json",
        _synthetic_rating_document("dry-run-sheet-a", DRY_RUN_RATER_A, expected_item_ids),
    )
    _write_json(
        ratings_dir / "rater-b.json",
        _synthetic_rating_document("dry-run-sheet-b", DRY_RUN_RATER_B, expected_item_ids),
    )
    _write_json(ratings_dir / "arbiter.json", _arbiter_document())

    resolved, excluded = _resolve(sheets, _load_arbiter(ratings_dir / "arbiter.json"))
    item_arms, item_cases = load_unblinding(out_dir / "unblinding.json")
    reports = _build_contrasts(resolved, excluded, item_arms, item_cases)
    ratings = _ratings_summary(resolved, excluded, synthetic=True)

    record = _run_record(
        mode=MODE_DRY_RUN,
        status=STATUS_DRY_RUN_COMPLETE,
        model="",
        budget=DRY_RUN_BUDGET,
        provider_calls=0,
        stub_calls=stub_calls,
        cases=case_set.case_ids,
        arms=arms,
        split_clean=leak_report.clean,
        reports=reports,
        ratings=ratings,
        synthetic=True,
    )
    _write_json(out_dir / "run.json", record)
    _write_json(out_dir / "significance.json", _contrasts_document(reports, synthetic=True))
    _write_text(
        out_dir / "significance.md",
        "# LC-P2-14 — significance (DRY RUN)\n\n"
        "> Synthetic ratings: every label is the protocol's `unknown`, so every\n"
        "> verdict is the not-significant path by rule. These rows are not a\n"
        "> measurement of any arm's capability.\n\n"
        + significance.render_report(reports[0])
        + "\n"
        + significance.render_report(reports[1]),
    )
    _write_text(
        out_dir / "report.md",
        _render_report(
            mode=MODE_DRY_RUN,
            status=STATUS_DRY_RUN_COMPLETE,
            model="",
            budget=DRY_RUN_BUDGET,
            provider_calls=0,
            stub_calls=stub_calls,
            cases=case_set.case_ids,
            arms=[arm.arm_id for arm in arms],
            split_clean=leak_report.clean,
            reports=reports,
            ratings=ratings,
        ),
    )
    return RunSummary(
        mode=MODE_DRY_RUN,
        status=STATUS_DRY_RUN_COMPLETE,
        out_dir=out_dir,
        artifacts=artifacts,
        provider_calls=0,
        stub_calls=stub_calls,
        model="",
        budget=DRY_RUN_BUDGET,
        cases=case_set.case_ids,
        arms=tuple(arm.arm_id for arm in arms),
        split_clean=leak_report.clean,
        contrasts=reports,
        ratings=ratings,
    )


def run_real(
    *,
    provider: ModelProvider,
    out_dir: Path,
    model: str,
    budget: str,
    cases: Sequence[CaseSpec],
    arms: Sequence[ArmConfiguration] | None = None,
) -> RunSummary:
    """Run the arms against a real provider and stop at AWAITING RATINGS.

    The provider is built by :func:`build_real_provider`, which refuses
    without an approved consent and a budget ceiling. This function trusts
    that boundary and does not re-check it: a provider that was built is a
    provider the owner authorised.

    The run writes artefacts, the blind packet, the unblinding map and a run
    record whose ``significance`` is the ``NOT RUN`` status. It does **not**
    score: scoring needs people, and :func:`run_score` is where their sheets
    enter.
    """
    if not model.strip():
        raise RealRunRefusedError("a real run must declare the model it is using")
    arms = tuple(arms if arms is not None else default_arms(model=model, budget=budget))
    case_set = CaseSet(tuple(cases))
    _check_configuration(arms)
    leak_report = _check_split(case_set.cases)
    if not leak_report.clean:
        raise RunRefusedError(
            "the split leaks, so nothing is run: "
            + "; ".join(f"{leak.shape}: {leak.detail}" for leak in leak_report.leaks)
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    sent: list[ArtifactRecord] = []
    try:
        artifacts, provider_calls = _record_artifacts(
            provider, arms, case_set.cases, on_each=sent.append
        )
    except OutboundRefusedError as error:
        # The answers already paid for are kept, and the record says how many
        # calls were spent before the refusal. A refused run that reported
        # zero after sending thirty would hide money it spent.
        _write_artifacts(out_dir, sent)
        record = _run_record(
            mode=MODE_REAL,
            status=STATUS_REFUSED,
            model=model,
            budget=budget,
            provider_calls=len(sent),
            stub_calls=0,
            cases=case_set.case_ids,
            arms=arms,
            split_clean=leak_report.clean,
            reports=(),
            ratings={},
            synthetic=False,
            refusal=str(error),
        )
        _write_json(out_dir / "run.json", record)
        raise
    _write_artifacts(out_dir, artifacts)
    _write_blind_packet(out_dir, artifacts, case_set.cases)
    _write_unblinding(out_dir, artifacts)

    ratings: dict[str, Any] = {}
    record = _run_record(
        mode=MODE_REAL,
        status=STATUS_AWAITING_RATINGS,
        model=model,
        budget=budget,
        provider_calls=provider_calls,
        stub_calls=0,
        cases=case_set.case_ids,
        arms=arms,
        split_clean=leak_report.clean,
        reports=(),
        ratings=ratings,
        synthetic=False,
    )
    _write_json(out_dir / "run.json", record)
    _write_text(
        out_dir / "report.md",
        _render_report(
            mode=MODE_REAL,
            status=STATUS_AWAITING_RATINGS,
            model=model,
            budget=budget,
            provider_calls=provider_calls,
            stub_calls=0,
            cases=case_set.case_ids,
            arms=[arm.arm_id for arm in arms],
            split_clean=leak_report.clean,
            reports=(),
            ratings=ratings,
        ),
    )
    return RunSummary(
        mode=MODE_REAL,
        status=STATUS_AWAITING_RATINGS,
        out_dir=out_dir,
        artifacts=artifacts,
        provider_calls=provider_calls,
        stub_calls=0,
        model=model,
        budget=budget,
        cases=case_set.case_ids,
        arms=tuple(arm.arm_id for arm in arms),
        split_clean=leak_report.clean,
        contrasts=(),
        ratings=ratings,
    )


def run_score(
    *,
    run_dir: Path,
    rater_a: Path,
    rater_b: Path,
    arbiter: Path | None = None,
    out_dir: Path | None = None,
) -> RunSummary:
    """Score a completed run with two rater sheets and an arbiter, then judge.

    The run directory must carry ``blind_packet.json``, ``unblinding.json``
    and ``run.json``. The two sheets are loaded by the production loader, so
    an incomplete sheet, a duplicated item or a sheet that names an arm is
    refused rather than repaired. The output is ``evaluated`` only when the
    resolution and both contrasts have been built; an excluded rating is
    carried in the denominators, not dropped.
    """
    destination = out_dir if out_dir is not None else run_dir
    destination.mkdir(parents=True, exist_ok=True)
    packet = json.loads((run_dir / "blind_packet.json").read_text(encoding="utf-8"))
    packet_items = packet.get("items")
    if not isinstance(packet_items, list) or not packet_items:
        raise ValueError("the blind packet carries no items")
    expected_item_ids = [str(item["item_id"]) for item in packet_items if isinstance(item, Mapping)]

    sheets = (
        blind_sheet.load_blind_sheet(
            json.loads(rater_a.read_text(encoding="utf-8")), expected_item_ids
        ),
        blind_sheet.load_blind_sheet(
            json.loads(rater_b.read_text(encoding="utf-8")), expected_item_ids
        ),
    )
    resolved, excluded = _resolve(sheets, _load_arbiter(arbiter))
    item_arms, item_cases = load_unblinding(run_dir / "unblinding.json")
    reports = _build_contrasts(resolved, excluded, item_arms, item_cases)
    ratings = _ratings_summary(resolved, excluded, synthetic=False)

    previous = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    model = str(previous.get("model", ""))
    budget = str(previous.get("budget", ""))
    provider_calls = int(previous.get("provider_calls", 0))
    stub_calls = int(previous.get("stub_calls", 0))
    cases = tuple(str(one) for one in previous.get("cases", []))
    split = previous.get("split")
    split_clean = bool(split.get("clean")) if isinstance(split, Mapping) else False
    raw_arms = previous.get("arms")
    if not isinstance(raw_arms, list) or not raw_arms:
        raise ValueError("the run record carries no arm configuration to score")
    previous_arms = tuple(
        ArmConfiguration.from_document(one) for one in raw_arms if isinstance(one, Mapping)
    )
    arm_ids = tuple(arm.arm_id for arm in previous_arms)

    record = _run_record(
        mode=MODE_SCORE,
        status=STATUS_EVALUATED,
        model=model,
        budget=budget,
        provider_calls=provider_calls,
        stub_calls=stub_calls,
        cases=cases,
        arms=previous_arms,
        split_clean=split_clean,
        reports=reports,
        ratings=ratings,
        synthetic=False,
    )
    _write_json(destination / "run.json", record)
    _write_json(destination / "significance.json", _contrasts_document(reports, synthetic=False))
    _write_text(
        destination / "significance.md",
        significance.render_report(reports[0]) + "\n" + significance.render_report(reports[1]),
    )
    _write_text(
        destination / "report.md",
        _render_report(
            mode=MODE_SCORE,
            status=STATUS_EVALUATED,
            model=model,
            budget=budget,
            provider_calls=provider_calls,
            stub_calls=stub_calls,
            cases=cases,
            arms=list(arm_ids),
            split_clean=split_clean,
            reports=reports,
            ratings=ratings,
        ),
    )
    return RunSummary(
        mode=MODE_SCORE,
        status=STATUS_EVALUATED,
        out_dir=destination,
        artifacts=(),
        provider_calls=provider_calls,
        stub_calls=stub_calls,
        model=model,
        budget=budget,
        cases=cases,
        arms=arm_ids,
        split_clean=split_clean,
        contrasts=reports,
        ratings=ratings,
    )


def missing_real_requirements(
    *,
    approvals: int | None,
    budget: RunBudget | None,
    model: str,
    usage_capture: UsageCapture | None,
) -> tuple[str, ...]:
    """Every reason a real run may not start, named in the order they are checked.

    The caller prints this and exits non-zero **before** constructing a
    provider. Keeping the check here rather than inside
    :func:`build_real_provider` lets the command line explain all the missing
    pieces at once instead of one exception at a time.
    """
    problems: list[str] = []
    if approvals is None or approvals <= 0:
        problems.append(
            "no owner approval: a real run needs an approved outbound consent "
            "for every request, and the driver will not construct a provider "
            "without one"
        )
    if budget is None or not _budget_has_ceiling(budget):
        problems.append(
            "no budget ceiling: a real run needs at least one ceiling "
            "(max_total_tokens or max_model_requests) before it may start"
        )
    if not model.strip():
        problems.append("no model declared")
    if usage_capture is None:
        problems.append(
            "no usage capture: without one every token count is Unknown and a "
            "token ceiling refuses to start, so the run would fail at its "
            "first request"
        )
    return tuple(problems)


def _budget_has_ceiling(budget: RunBudget) -> bool:
    """Whether a budget bounds anything other than a tool argument's size."""
    return any(
        value is not None
        for value in (
            budget.max_tool_calls,
            budget.max_model_requests,
            budget.max_total_tokens,
            budget.max_cost_usd,
            budget.max_wall_clock_s,
            budget.max_tool_call_seconds,
        )
    )


def build_real_provider(
    settings: ProviderSettings,
    *,
    consent: OutboundConsent | None,
    budget: RunBudget | None,
    usage_capture: UsageCapture | None,
    http_client: Any | None = None,
) -> PydanticAiModelProvider:
    """The only place this driver constructs a real provider.

    The refusals are the point of the function:

    * **no consent** — the provider is unbuildable without one (ADR-0006), and
      the driver does not have a second path around the outbound bridge;
    * **no ceiling** — a budget that bounds nothing is not a budget, and a
      real run is not authorised by an unbounded one;
    * **no usage capture** — the provider would report every token count as
      ``Unknown`` and the first ceiling check would refuse the run, so the
      caller is told now rather than after a request has been prepared.

    ``http_client`` is where the usage sniffer is mounted; the caller owns it
    because the same client has to serve the probe and the run.
    """
    if consent is None:
        raise RealRunRefusedError(
            "a real run cannot be built without an approved outbound consent; "
            "the provider's consent port is a required constructor argument "
            "(ADR-0006), and this driver will not bypass it"
        )
    if budget is None or not _budget_has_ceiling(budget):
        raise RealRunRefusedError(
            "a real run cannot be built without a budget ceiling; an unbounded "
            "budget does not authorise spending"
        )
    if usage_capture is None:
        raise RealRunRefusedError(
            "a real run cannot be built without a usage capture; without one "
            "every token count is Unknown and the token ceiling refuses to start"
        )
    model = build_model(settings, http_client=http_client)
    return PydanticAiModelProvider(
        model=model,
        consent=consent,
        usage_capture=usage_capture,
        budget=budget,
    )
