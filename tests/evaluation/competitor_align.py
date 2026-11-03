"""LC-P2-18's aligner: two sides' raw outputs, one comparable shape.

**What this module does, and what it refuses to do.** A side's raw run
output is a directory of per-case artifacts (the shape
:class:`~tests.evaluation.competitor_paperqa_run.ArtifactLayout`
describes) beside a basis declaration. The aligner turns two such
directories into the shape ``comparison.py`` reads — two
:class:`~tests.evaluation.comparison.ComparisonBasis` documents whose
metrics are computed from the artifacts **and the package's answer keys
and nothing else** (brief §5 clause 5) — and then asks
:func:`~tests.evaluation.comparison.assess` the six-condition question.

**The refusals are the point.** An aligner that scored a lopsided input
would be the mechanism by which a broken run produces a number anyway.
So every way the inputs can fail to be two complete sides is a refusal,
collected and reported, never a defaulted score:

* a task face missing from either side (or the package);
* a case missing, extra, or **misfiled** — an artifact whose declared
  case does not match the file it sits in is a cell written under the
  wrong name, and scoring it would be scoring the corpus the aligner
  wishes it had;
* an answer-key version pin that does not match the package — a side
  that ran against different keys ran a different corpus;
* a run record that does not name this package's manifest hash;
* a scoring method outside the closed table.

**The scoring methods are a closed table, and their honesty is
recorded.** Per task face, exactly one mechanical method exists, keyed by
the ``scoring`` field each artifact declares:

* ``numeric-cell-recall`` — the adapter's recall rule
  (:func:`~tests.evaluation.paperqa_adapter.score_artifact`): the key's
  expected statistics recalled among the numbers the answer contains.
  Deliberately flattering to a free-text answer; the preparation record
  holds the reasoning.
* ``numeric-cell-exactness`` — our side's cell-by-cell form: the artifact
  carries the per-cell outcomes its own selection machinery produced, and
  the aligner counts them. It verifies structure (a name per cell, no
  duplicates, booleans) and invents no cell.
* ``abstention-mechanical`` — the one mechanical rule the no-evidence
  key supports: an answer that contains any of the key's
  ``no_fabricated_value`` numbers scores 0, anything else scores 1. The
  key's ``citation_resolves`` check has no mechanical reading for free
  text and is not scored; and the rule is **strict against the
  competitor** in one recorded way — an honest abstention that merely
  mentions a forbidden value (50 mM buffer concentration, 37 °C) in
  passing also scores 0. The artifact keeps the verbatim answer so a
  reviewer can re-read it; the record states the loss rather than
  hiding it.
* ``recovery-surface`` — scored from the face's surface declaration: a
  side that declares an absent surface scores 0 over the four cases
  (the brief rules that zero a fact about the competitor's scope), and a
  side that declares a present surface must carry all four cases'
  outcomes, each a boolean it observed, which the aligner counts.

**No ranking, ever.** The aligner returns what ``assess`` and
:func:`~tests.evaluation.comparison.pairs` return — comparable or not,
with reasons, and metric pairs that share a name. It has no aggregate
and no winner.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .comparison import ComparisonBasis, assess, pairs
from .competitor_package import (
    PACKAGE_SCHEMA,
    PackageInvalidError,
    package_manifest_sha256,
    task_case_files,
    validate_package,
)
from .competitor_paperqa_run import (
    SURFACE_ABSENT,
    ArtifactLayout,
)
from .model import ComparisonOutcome
from .paperqa_adapter import extract_numbers, score_artifact

__all__ = [
    "METHOD_NUMERIC_CELL_EXACTNESS",
    "METHOD_NUMERIC_CELL_RECALL",
    "METRIC_BY_METHOD",
    "AlignmentOutcome",
    "AlignmentRefusedError",
    "align",
]

#: The closed scoring-method table. A face's artifacts may declare one of
#: its face's methods and nothing else; a method the table does not name
#: is a refusal, never a default.
METHOD_NUMERIC_CELL_RECALL: Final = "numeric-cell-recall"
METHOD_NUMERIC_CELL_EXACTNESS: Final = "numeric-cell-exactness"
METHOD_ABSTENTION_MECHANICAL: Final = "abstention-mechanical"
METHOD_RECOVERY_SURFACE: Final = "recovery-surface"

#: Per face, the methods its artifacts may declare. Our side's numeric
#: artifacts carry their own cell-by-cell outcomes; a competitor's carry
#: free text scored by recall. Both names map to the metric the frozen
#: baseline's shape expects on that side.
METHODS_BY_FACE: Final[dict[str, tuple[str, ...]]] = {
    "numeric-extraction": (METHOD_NUMERIC_CELL_RECALL, METHOD_NUMERIC_CELL_EXACTNESS),
    "unsupported-claim-detection": (METHOD_ABSTENTION_MECHANICAL,),
    "recovery-correctness": (METHOD_RECOVERY_SURFACE,),
}

#: The metric name each method's score is reported under. Task 1's two
#: methods map to *different* metric names on purpose — cell exactness and
#: statistic recall have different denominators, and one name over two
#: denominators would be one number pretending to be another (the same
#: ruling the comparison driver's stub metric already records). Tasks 2
#: and 3 measure the same thing on both sides, so their one metric name is
#: shared, and pairs() can pair them.
METRIC_BY_METHOD: Final[dict[str, str]] = {
    METHOD_NUMERIC_CELL_RECALL: "numeric-extraction-recall",
    METHOD_NUMERIC_CELL_EXACTNESS: "numeric-extraction-exactness",
    METHOD_ABSTENTION_MECHANICAL: "unsupported-claim-detection",
    METHOD_RECOVERY_SURFACE: "recovery-correctness",
}


class AlignmentRefusedError(RuntimeError):
    """The two sides cannot be aligned, and no score will be produced."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True, slots=True)
class AlignmentOutcome:
    """What a successful alignment hands to the report and the record."""

    #: The two sides, in the shape ``comparison.py`` reads.
    our_basis: ComparisonBasis
    competitor_basis: ComparisonBasis
    #: Each side's metrics: metric name to numerator/denominator.
    our_metrics: dict[str, dict[str, int]]
    competitor_metrics: dict[str, dict[str, int]]
    #: The six-condition verdict over the two bases.
    comparison: ComparisonOutcome
    #: The package manifest's hash both sides were checked against.
    package_manifest_sha256: str

    def as_document(self) -> dict[str, Any]:
        """The outcome as a JSON document, for the record and the report."""
        to_pairs_shape = {
            name: (row["numerator"], row["denominator"]) for name, row in self.our_metrics.items()
        }
        competitor_shape = {
            name: (row["numerator"], row["denominator"])
            for name, row in self.competitor_metrics.items()
        }
        pair_rows = pairs(to_pairs_shape, competitor_shape)
        return {
            "schema": PACKAGE_SCHEMA,
            "package_manifest_sha256": self.package_manifest_sha256,
            "comparable": self.comparison.comparable,
            "conditions": [
                {
                    "name": check.name,
                    "met": check.met,
                    "detail": check.detail,
                }
                for check in self.comparison.conditions
            ],
            "our_metrics": self.our_metrics,
            "competitor_metrics": self.competitor_metrics,
            "pairs": [{"metric": name, "printed": printed} for name, printed in pair_rows],
            "our_basis": {
                "label": self.our_basis.label,
                "model": self.our_basis.model,
                "budget": self.our_basis.budget,
                "limitations": self.our_basis.limitations,
            },
            "competitor_basis": {
                "label": self.competitor_basis.label,
                "model": self.competitor_basis.model,
                "budget": self.competitor_basis.budget,
                "limitations": self.competitor_basis.limitations,
            },
        }


def _read_json(path: Path, reasons: list[str], what: str) -> dict[str, Any] | None:
    if not path.is_file():
        reasons.append(f"missing {what}: {path}")
        return None
    document: dict[str, Any] | None
    try:
        document = json.loads(path.read_bytes())
    except (json.JSONDecodeError, ValueError) as error:
        reasons.append(f"{what} is not valid JSON ({path}): {error}")
        return None
    return document


def _check_key_versions(side_dir: Path, package_dir: Path, reasons: list[str]) -> None:
    """A side's key pins must equal the package's, or the side ran another corpus."""
    side_versions = _read_json(
        ArtifactLayout(root=side_dir).key_versions_path,
        reasons,
        "the side's key-version pins",
    )
    if side_versions is None:
        return
    expected: dict[str, str] = {}
    for face in METHODS_BY_FACE:
        expected.update(task_case_files(package_dir, face))
    for relpath, digest in sorted(expected.items()):
        if side_versions.get(relpath) != digest:
            reasons.append(
                f"{side_dir.name}: answer key {relpath} is pinned to "
                f"{side_versions.get(relpath)!r} but the package holds {digest}"
            )
    for relpath in sorted(side_versions):
        if relpath not in expected:
            reasons.append(
                f"{side_dir.name}: key-version pin for {relpath} names no case in the package"
            )


def _check_run_document(side_dir: Path, manifest_sha: str, reasons: list[str]) -> None:
    """A side must name the package it ran, by its manifest hash."""
    run = _read_json(
        ArtifactLayout(root=side_dir).run_document_path,
        reasons,
        "the side's run record",
    )
    if run is None:
        return
    if run.get("package_manifest_sha256") != manifest_sha:
        reasons.append(
            f"{side_dir.name}: run record names package manifest "
            f"{run.get('package_manifest_sha256')!r}, not this package's {manifest_sha}"
        )


def _read_side_artifacts(
    side_dir: Path, reasons: list[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Every answer artifact of a side, keyed face then case.

    A file under the wrong face directory, a file whose declared case does
    not match its name, or a file that is not an artifact of the closed
    method table is collected as a refusal reason and left out of the
    returned artifacts — the aligner never scores an artifact it has
    objected to.
    """
    artifacts: dict[str, dict[str, dict[str, Any]]] = {}
    answers_dir = side_dir / "answers"
    if not answers_dir.is_dir():
        reasons.append(f"{side_dir.name}: no answers/ directory")
        return artifacts
    for face_dir in sorted(path for path in answers_dir.iterdir() if path.is_dir()):
        face = face_dir.name
        if face not in METHODS_BY_FACE:
            reasons.append(
                f"{side_dir.name}: answers/ holds directory {face!r}, which is not a task face"
            )
            continue
        artifacts.setdefault(face, {})
        for path in sorted(face_dir.glob("*.json")):
            document = _read_json(path, reasons, f"artifact {face}/{path.name}")
            if document is None:
                continue
            case = path.stem
            if document.get("case") != case or document.get("face") != face:
                reasons.append(
                    f"{side_dir.name}: artifact answers/{face}/{path.name} declares "
                    f"face={document.get('face')!r} case={document.get('case')!r} — "
                    "an artifact filed under a name it does not declare"
                )
                continue
            declared = document.get("scoring")
            if declared not in METHODS_BY_FACE[face]:
                reasons.append(
                    f"{side_dir.name}: artifact {face}/{case} declares scoring "
                    f"{declared!r}; the face allows {list(METHODS_BY_FACE[face])}"
                )
                continue
            artifacts[face][case] = document
    return artifacts


def _check_coverage(
    side_dir: Path,
    artifacts: dict[str, dict[str, dict[str, Any]]],
    package_dir: Path,
    reasons: list[str],
) -> None:
    """Each face's artifacts must cover exactly the package's cases.

    A missing case is a hole a score would hide; an extra case is a case
    the corpus does not hold. Both are refusals. The recovery face is the
    one exception, and its coverage is checked by :func:`_score_recovery`
    instead: a side that declares an absent surface carries no per-case
    artifacts at all, and a side that declares a present surface must
    carry all four.
    """
    for face in METHODS_BY_FACE:
        if face == "recovery-correctness":
            continue
        expected_cases = {Path(name).name for name in task_case_files(package_dir, face)}
        expected_cases = {
            name.removesuffix(".expected.json").removesuffix(".json") for name in expected_cases
        }
        actual = set(artifacts.get(face, {}))
        for case in sorted(expected_cases - actual):
            reasons.append(f"{side_dir.name}: task face {face} is missing case {case}")
        for case in sorted(actual - expected_cases):
            reasons.append(
                f"{side_dir.name}: task face {face} holds case {case}, which the package does not"
            )


def _score_numeric_recall(document: dict[str, Any], key: dict[str, Any]) -> tuple[int, int]:
    """The adapter's recall rule, over the captured text and the package's key.

    The artifact already carries the adapter's shape (``status`` and
    ``answer``), so the recorded artifact is re-scored exactly as the run
    captured it — no conversion, no repair.
    """
    case_score = score_artifact(document, key)
    return case_score.matched, case_score.expected


def _score_numeric_exactness(document: dict[str, Any]) -> tuple[int, int]:
    """Count the per-cell outcomes the artifact carries; invent none."""
    cells = document.get("cells")
    if not isinstance(cells, list) or not cells:
        raise AlignmentRefusedError(
            (
                f"artifact {document.get('case')} declares "
                f"{METHOD_NUMERIC_CELL_EXACTNESS} but carries no cells list",
            )
        )
    seen: set[str] = set()
    recalled = 0
    for cell in cells:
        if not isinstance(cell, dict):
            raise AlignmentRefusedError(
                (f"artifact {document.get('case')} has a cell that is not an object",)
            )
        name = cell.get("cell")
        if not isinstance(name, str) or not name:
            raise AlignmentRefusedError(
                (f"artifact {document.get('case')} has a cell with no name",)
            )
        if name in seen:
            raise AlignmentRefusedError(
                (f"artifact {document.get('case')} names cell {name!r} twice",)
            )
        seen.add(name)
        if not isinstance(cell.get("ok"), bool):
            raise AlignmentRefusedError(
                (f"artifact {document.get('case')} cell {name!r} carries no ok verdict",)
            )
        if cell["ok"]:
            recalled += 1
    return recalled, len(cells)


def _score_abstention(document: dict[str, Any], key: dict[str, Any]) -> tuple[int, int]:
    """The no-evidence key's one mechanical rule, and its recorded strictness.

    Any of the key's ``no_fabricated_value`` numbers appearing in the
    answer scores 0; anything else scores 1. The rule cannot read prose
    intent: an honest abstention that mentions a forbidden value in
    passing also scores 0. The verbatim answer stays in the artifact for
    exactly that re-reading.
    """
    answer_text = document.get("answer")
    if not isinstance(answer_text, str):
        raise AlignmentRefusedError(
            (
                f"artifact {document.get('case')} declares {METHOD_ABSTENTION_MECHANICAL} "
                "but carries no answer text",
            )
        )
    forbidden = [
        float(check["value"])
        for check in key.get("expected_artifact_checks", [])
        if check.get("kind") == "no_fabricated_value"
    ]
    numbers = [float(value) for value in extract_numbers(answer_text)]
    for value in numbers:
        for banned in forbidden:
            if math.isclose(value, banned, rel_tol=1e-9, abs_tol=1e-9):
                return 0, 1
    return 1, 1


def _score_recovery(
    side_dir: Path,
    face_artifacts: dict[str, dict[str, Any]],
    package_cases: set[str],
    reasons: list[str],
) -> tuple[int, int] | None:
    """Score the recovery face from its surface declaration, or refuse.

    An absent surface scores zero over the package's cases — the brief's
    own ruling (§1) that a competitor's zero on a face it has no surface
    for is a fact about the competitor's scope. A present surface must
    carry every case and each case's observed boolean.
    """
    surface_path = ArtifactLayout(root=side_dir).surface_path("recovery-correctness")
    if not surface_path.is_file():
        reasons.append(
            f"{side_dir.name}: task face recovery-correctness carries neither "
            f"a per-case artifact nor a surface declaration at {surface_path.name}"
        )
        return None
    declaration = _read_json(surface_path, reasons, "the recovery surface declaration")
    if declaration is None:
        return None
    if declaration.get("surface") == SURFACE_ABSENT:
        return 0, len(package_cases)
    if declaration.get("surface") != "present":
        reasons.append(
            f"{side_dir.name}: recovery surface declaration says "
            f"{declaration.get('surface')!r}; it must say 'present' or 'absent'"
        )
        return None
    held = 0
    for case in sorted(package_cases):
        document = face_artifacts.get(case)
        if document is None:
            reasons.append(
                f"{side_dir.name}: recovery surface is present but case {case} carries no artifact"
            )
            return None
        verdict = document.get("held")
        if not isinstance(verdict, bool):
            reasons.append(f"{side_dir.name}: recovery case {case} carries no boolean held verdict")
            return None
        if verdict:
            held += 1
    return held, len(package_cases)


def _score_face(
    side_dir: Path,
    face: str,
    face_artifacts: dict[str, dict[str, Any]],
    package_dir: Path,
    reasons: list[str],
) -> dict[str, dict[str, int]]:
    """One face's metrics, from its artifacts and the package's keys.

    All of a face's artifacts on one side must declare the **same**
    method: the face's score is one number over the face's cases, and a
    score assembled from two different mechanical rules would be two
    numbers under one name.
    """
    metrics: dict[str, dict[str, int]] = {}
    package_cases = {
        Path(name).name.removesuffix(".expected.json").removesuffix(".json")
        for name in task_case_files(package_dir, face)
    }
    if face == "recovery-correctness":
        score = _score_recovery(side_dir, face_artifacts, package_cases, reasons)
        if score is None:
            return metrics
        numerator, denominator = score
        metrics[METRIC_BY_METHOD[METHOD_RECOVERY_SURFACE]] = {
            "numerator": numerator,
            "denominator": denominator,
        }
        return metrics
    methods = {str(document["scoring"]) for document in face_artifacts.values()}
    if not methods:
        reasons.append(f"{side_dir.name}: task face {face} carries no artifacts to score")
        return metrics
    if len(methods) > 1:
        reasons.append(
            f"{side_dir.name}: task face {face} mixes scoring methods {sorted(methods)}; "
            "one face, one method"
        )
        return metrics
    method = methods.pop()
    numerator = 0
    denominator = 0
    for case in sorted(face_artifacts):
        document = face_artifacts[case]
        key_relpath = next(
            name
            for name in task_case_files(package_dir, face)
            if Path(name).name.removesuffix(".expected.json").removesuffix(".json") == case
        )
        key = json.loads((package_dir / "tasks" / key_relpath).read_bytes())
        if method == METHOD_NUMERIC_CELL_RECALL:
            case_numerator, case_denominator = _score_numeric_recall(document, key)
        elif method == METHOD_NUMERIC_CELL_EXACTNESS:
            case_numerator, case_denominator = _score_numeric_exactness(document)
        else:
            case_numerator, case_denominator = _score_abstention(document, key)
        numerator += case_numerator
        denominator += case_denominator
    if denominator:
        metrics[METRIC_BY_METHOD[method]] = {
            "numerator": numerator,
            "denominator": denominator,
        }
    return metrics


def _read_basis(side_dir: Path, reasons: list[str]) -> ComparisonBasis | None:
    """A side's basis declaration, or a collected reason."""
    document = _read_json(
        ArtifactLayout(root=side_dir).basis_document_path,
        reasons,
        "the side's basis declaration",
    )
    if document is None:
        return None
    return ComparisonBasis.from_document(document, side_dir.name)


def align(package_dir: Path, our_dir: Path, competitor_dir: Path) -> AlignmentOutcome:
    """Align two sides' raw outputs over one package, or refuse.

    Every refusal is collected, so a reader sees the whole shape of what
    is wrong rather than the first thing; the aligner raises once, with
    all of them, and produces no metrics on any refusal.
    """
    reasons: list[str] = []
    try:
        validate_package(package_dir)
    except PackageInvalidError as error:
        raise AlignmentRefusedError(error.reasons) from error
    manifest_sha = package_manifest_sha256(package_dir)

    for side_dir in (our_dir, competitor_dir):
        _check_run_document(side_dir, manifest_sha, reasons)
        _check_key_versions(side_dir, package_dir, reasons)

    our_artifacts = _read_side_artifacts(our_dir, reasons)
    competitor_artifacts = _read_side_artifacts(competitor_dir, reasons)
    for side_dir, artifacts in ((our_dir, our_artifacts), (competitor_dir, competitor_artifacts)):
        _check_coverage(side_dir, artifacts, package_dir, reasons)

    our_metrics: dict[str, dict[str, int]] = {}
    competitor_metrics: dict[str, dict[str, int]] = {}
    if not reasons:
        for face in METHODS_BY_FACE:
            our_metrics.update(
                _score_face(our_dir, face, our_artifacts.get(face, {}), package_dir, reasons)
            )
            competitor_metrics.update(
                _score_face(
                    competitor_dir, face, competitor_artifacts.get(face, {}), package_dir, reasons
                )
            )

    our_basis = _read_basis(our_dir, reasons)
    competitor_basis = _read_basis(competitor_dir, reasons)

    if reasons or our_basis is None or competitor_basis is None:
        raise AlignmentRefusedError(tuple(reasons))

    comparison = assess(our_basis, competitor_basis)
    return AlignmentOutcome(
        our_basis=our_basis,
        competitor_basis=competitor_basis,
        our_metrics=our_metrics,
        competitor_metrics=competitor_metrics,
        comparison=comparison,
        package_manifest_sha256=manifest_sha,
    )
