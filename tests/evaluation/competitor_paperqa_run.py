"""LC-P2-18's paper-qa side: the run scaffold, planned offline.

**What this module is.** The machinery the competitor side's run needs
before any provider is contacted: the **call plan** (what would be called,
for which cases, at least how many times), the **authorization gate**
(live mode refuses to start without the owner's approval file), and the
**artifact shape** every case's answer is captured into. The real
execution — importing paper-qa, driving its pipeline against a live
model — lives in ``scripts/run_paperqa_competitor.py``, which runs only
in the isolated paper-qa environment
(``docs/acceptance/LC-P2-18-preparation.md``); this module never imports
paper-qa, so the repository's own tests can hold every shape and refusal
without the competitor installed.

**What dry mode can honestly be.** Reading the package, validating it,
and printing the call plan — no network, no credentials, no spend. The
plan is the thing the owner approves a budget against, so it states a
**lower bound** on provider calls (paper-qa's per-case agent fan-out is a
runtime verification, brief §4) and names the task face that plans **zero**
calls: ``recovery-correctness``.

**Why recovery plans zero calls, and says so rather than faking a
question.** The crash windows are a capability of an executor with
transactional recovery; paper-qa's interface is documents in, answers
out. Asking it a crash-recovery "question" would produce prose about
documents — an answer with no surface to be right or wrong about. The
brief already rules this (§1): a competitor's zero on a task it has no
surface for is a fact about the competitor's scope, reported as such.
So the plan records ``surface: absent`` for that face, the run writes a
surface declaration instead of artifacts, and the aligner scores the
face from that declaration — nothing is invented to look like an answer.

**The live gate is a refusal, not a warning.** No credential is read and
no provider is contacted by anything in this module; live mode's first
act is checking for the owner's approval file, and without it the run
stops before the competitor is even imported. The approval file carries
the budget string, which both sides must declare identically (comparison
condition 4).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .competitor_package import (
    PACKAGE_SCHEMA,
    package_manifest_sha256,
    read_manifest,
    task_case_files,
    validate_package,
)

__all__ = [
    "DRY_MODE",
    "LIVE_MODE",
    "MODES",
    "SURFACE_ABSENT",
    "SURFACE_DOCUMENT_QA",
    "ArtifactLayout",
    "CallPlan",
    "LiveRunNotAuthorizedError",
    "PlannedCase",
    "PlannedFace",
    "build_call_plan",
    "require_live_authorization",
    "write_surface_declaration",
]

#: The runner's two modes. ``dry`` validates and plans; ``live`` is the
#: mode that spends, and it is gated.
DRY_MODE: Final = "dry"
LIVE_MODE: Final = "live"
MODES: Final = (DRY_MODE, LIVE_MODE)

#: Surface declarations — what the competitor's interface can be asked.
SURFACE_DOCUMENT_QA: Final = "document-qa"
SURFACE_ABSENT: Final = "absent"

#: The scoring method each face's answers are captured under. The aligner
#: dispatches on this name (its method table is closed); an artifact that
#: names a method outside it is refused, not scored by a default.
SCORING_BY_FACE: Final[dict[str, str]] = {
    "numeric-extraction": "numeric-cell-recall",
    "unsupported-claim-detection": "abstention-mechanical",
    "recovery-correctness": "recovery-surface",
}

#: The minimum completion calls a document-QA case makes: ingest is local
#: (the pinned paper-qa's sparse embedder, measured in the preparation
#: record), one query, one completion. Paper-qa's internal agent may call
#: more; that fan-out is a runtime verification, never an assumption.
CALLS_PER_DOCUMENT_QA_CASE: Final = 1


class LiveRunNotAuthorizedError(RuntimeError):
    """A live run was requested without the owner's approval file.

    A real run spends provider money on both sides, and that is the
    owner's call (brief §6). The refusal is the gate's whole point: the
    run cannot begin, and nothing has been spent.
    """


@dataclass(frozen=True, slots=True)
class PlannedCase:
    """One case a live run would put to the competitor."""

    #: The task face the case belongs to.
    face: str
    #: The case's id — the fixture name, question id, or crash point.
    case: str
    #: The package-relative question file the case is asked through;
    #: empty for a face whose surface is absent.
    question_file: str
    #: Lower bound on completion calls this case costs.
    provider_calls_min: int


@dataclass(frozen=True, slots=True)
class PlannedFace:
    """One task face of the call plan."""

    face: str
    #: What the competitor's interface offers this face.
    surface: str
    cases: tuple[PlannedCase, ...]


@dataclass(frozen=True, slots=True)
class CallPlan:
    """The three faces, planned: what a live run would call, and why not."""

    faces: tuple[PlannedFace, ...]
    #: The package manifest's SHA-256 — the plan is for *this* corpus.
    package_manifest_sha256: str

    @property
    def provider_calls_min(self) -> int:
        """The run's minimum completion-call count across all faces."""
        return sum(case.provider_calls_min for planned in self.faces for case in planned.cases)

    def as_document(self) -> dict[str, Any]:
        """The plan as a JSON document, for the dry run's output."""
        return {
            "schema": PACKAGE_SCHEMA,
            "package_manifest_sha256": self.package_manifest_sha256,
            "mode": DRY_MODE,
            "provider_calls_min": self.provider_calls_min,
            "faces": [
                {
                    "face": planned.face,
                    "surface": planned.surface,
                    "case_count": len(planned.cases),
                    "provider_calls_min": sum(case.provider_calls_min for case in planned.cases),
                    "cases": [
                        {
                            "case": case.case,
                            "question_file": case.question_file,
                            "provider_calls_min": case.provider_calls_min,
                        }
                        for case in planned.cases
                    ],
                }
                for planned in self.faces
            ],
        }


def build_call_plan(package_dir: Path) -> CallPlan:
    """Plan the competitor run over a validated package.

    The plan's case lists come from the package's answer keys — one case
    per key, the same files both sides were handed — so a plan cannot
    silently cover a different corpus than the package declares.
    """
    validate_package(package_dir)
    manifest_sha = package_manifest_sha256(package_dir)

    numeric_keys = task_case_files(package_dir, "numeric-extraction")
    abstention_keys = task_case_files(package_dir, "unsupported-claim-detection")

    numeric_cases = tuple(
        PlannedCase(
            face="numeric-extraction",
            case=Path(relpath).name.removesuffix(".expected.json"),
            question_file=(
                f"numeric-extraction/questions/"
                f"{Path(relpath).name.removesuffix('.expected.json')}.question.txt"
            ),
            provider_calls_min=CALLS_PER_DOCUMENT_QA_CASE,
        )
        for relpath in sorted(numeric_keys)
    )
    abstention_cases = tuple(
        PlannedCase(
            face="unsupported-claim-detection",
            case=Path(relpath).name.removesuffix(".json"),
            question_file=(
                "unsupported-claim-detection/questions/"
                f"{Path(relpath).name.removesuffix('.json')}.question.txt"
            ),
            provider_calls_min=CALLS_PER_DOCUMENT_QA_CASE,
        )
        for relpath in sorted(abstention_keys)
    )

    return CallPlan(
        faces=(
            PlannedFace(
                face="numeric-extraction",
                surface=SURFACE_DOCUMENT_QA,
                cases=numeric_cases,
            ),
            PlannedFace(
                face="unsupported-claim-detection",
                surface=SURFACE_DOCUMENT_QA,
                cases=abstention_cases,
            ),
            PlannedFace(
                face="recovery-correctness",
                surface=SURFACE_ABSENT,
                cases=(),
            ),
        ),
        package_manifest_sha256=manifest_sha,
    )


def require_live_authorization(approval_path: Path) -> dict[str, Any]:
    """Read the owner's approval file, or refuse the live run.

    The file is a JSON document with a non-empty ``budget`` (the string
    both sides declare) and an ``approved_by``. It lives outside the
    repository with the credentials; nothing here reads those.
    """
    if not approval_path.is_file():
        raise LiveRunNotAuthorizedError(
            f"live mode requires the owner's approval file at {approval_path}; "
            "a real run spends provider money and that is the owner's call "
            "(brief §6). Nothing was called and nothing was spent."
        )
    document: dict[str, Any] = json.loads(approval_path.read_bytes())
    missing = [field for field in ("budget", "approved_by") if not document.get(field)]
    if missing:
        raise LiveRunNotAuthorizedError(
            f"approval file {approval_path} does not declare: {missing}"
        )
    return document


def write_surface_declaration(artifacts_dir: Path, plan: CallPlan, reason: str) -> Path:
    """Write the recovery face's surface declaration for an absent surface.

    The declaration is the artifact the aligner scores the face from: the
    competitor offers no surface for transactional recovery, and the brief
    rules the zero a fact about the competitor's scope. Writing it here,
    at run time, keeps the aligner from having to re-derive the fact — and
    keeps the run's own record honest about what it did not attempt.
    """
    absent_faces = [planned.face for planned in plan.faces if planned.surface == SURFACE_ABSENT]
    document = {
        "surface": SURFACE_ABSENT,
        "faces": absent_faces,
        "reason": reason,
        "scoring": {face: SCORING_BY_FACE[face] for face in absent_faces},
    }
    target = artifacts_dir / "recovery-correctness" / "surface.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return target


@dataclass(frozen=True, slots=True)
class ArtifactLayout:
    """Where a side's run writes what, and the names the aligner reads.

    Both sides write this layout, so the aligner's walk is one function
    over two directories. ``answers/`` holds one artifact per case; a face
    whose surface is absent holds its ``surface.json`` instead.
    """

    root: Path

    @property
    def run_document_path(self) -> Path:
        return self.root / "run.json"

    @property
    def basis_document_path(self) -> Path:
        return self.root / "basis.json"

    @property
    def key_versions_path(self) -> Path:
        return self.root / "key-versions.json"

    def answer_path(self, face: str, case: str) -> Path:
        return self.root / "answers" / face / f"{case}.json"

    def surface_path(self, face: str) -> Path:
        return self.root / face / "surface.json"

    def write_key_versions(self, package_dir: Path) -> dict[str, str]:
        """Copy the package's answer-key hashes as this side's version pins.

        A side records the keys it ran against; the aligner later refuses
        any side whose pins do not match the package it is being aligned
        over — the content-pin rule the comparison's condition 2 already
        applies to the baseline.
        """
        keys: dict[str, str] = {}
        for face in SCORING_BY_FACE:
            keys.update(task_case_files(package_dir, face))
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "key-versions.json").write_text(
            json.dumps(keys, indent=2, sort_keys=True) + "\n"
        )
        return keys


def case_input_files(package_dir: Path, face: str, case: str) -> dict[str, bytes]:
    """The task materials one case is put to the competitor with.

    The answer keys are deliberately **not** here: a key is what the
    aligner scores against, and handing it to the executed system would be
    handing it the answer. A case's inputs are its material (the fixture's
    bytes, or the no-evidence corpus's two files) and the question text.
    """
    manifest = read_manifest(package_dir)
    inputs: dict[str, bytes] = {}
    for relpath, _digest in sorted(manifest["files"].items()):
        if not relpath.startswith(f"{face}/"):
            continue
        name = Path(relpath).name
        if relpath.startswith(f"{face}/fixtures/"):
            if name != case:
                continue
        elif relpath.startswith(f"{face}/material/"):
            pass
        elif relpath.startswith(f"{face}/questions/"):
            if name != f"{case}.question.txt":
                continue
        else:
            # answer-keys/, and anything else, is not a case input.
            continue
        inputs[name] = (package_dir / "tasks" / relpath).read_bytes()
    return inputs


def run_planned_cases(
    plan: CallPlan,
    package_dir: Path,
    artifacts_dir: Path,
    *,
    execute_case: Callable[[PlannedCase, dict[str, bytes]], str],
) -> dict[str, Any]:
    """Put every planned case to the competitor and capture the answers.

    ``execute_case`` is the injected seam: the live script hands the real
    paper-qa pipeline, a test hands a stub. The callback receives the
    case's input files as bytes (fixture or material, plus the question
    text) and returns the answer **verbatim** — nothing here parses,
    repairs or reformats an answer; capture is the run's whole job.
    """
    layout = ArtifactLayout(root=artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for planned in plan.faces:
        if planned.surface == SURFACE_ABSENT:
            path = write_surface_declaration(
                artifacts_dir,
                plan,
                "the competitor's interface is documents-in, answers-out; it "
                "has no executor to inject a crash into, and the brief rules "
                "the face's zero a fact about the competitor's scope",
            )
            written.append(path.relative_to(artifacts_dir).as_posix())
            continue
        for case in planned.cases:
            inputs = case_input_files(package_dir, planned.face, case.case)
            answer_text = execute_case(case, inputs)
            # The artifact carries the adapter's shape (status/answer, so
            # score_artifact can re-score it from the record alone) plus the
            # alignment fields the aligner files it by. The answer is
            # verbatim; capture is the run's whole job.
            document = {
                "face": planned.face,
                "case": case.case,
                "question_file": case.question_file,
                "fixture": case.case,
                "status": "answered",
                "answer": answer_text,
                "scoring": SCORING_BY_FACE[planned.face],
            }
            path = layout.answer_path(planned.face, case.case)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
            written.append(path.relative_to(artifacts_dir).as_posix())
    return {"written": written, "package_manifest_sha256": plan.package_manifest_sha256}
