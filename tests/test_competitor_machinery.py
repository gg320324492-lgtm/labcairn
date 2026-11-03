"""LC-P2-18's competitor machinery, watched end to end.

**What this file watches.** The three modules the competitor baseline's
machinery is made of:

* :mod:`tests.evaluation.competitor_package` — the two-side task package:
  every case of the three task faces present, manifest hashes true, and
  two builds byte-identical;
* :mod:`tests.evaluation.competitor_paperqa_run` — the runner scaffold:
  a call plan that covers exactly the package's cases, twelve minimum
  provider calls (the recovery face plans none), and a live gate that
  refuses before anything is imported;
* :mod:`tests.evaluation.competitor_align` — the aligner: two sides'
  artifacts scored by the closed method table and aligned into the
  six-condition shape, **or refused** — a missing face, a misfiled
  artifact, a key pin that does not match the package, or a scoring
  method outside the table refuses the alignment instead of scoring it.

**The mutations below are the witnesses' teeth.** Each refusal test
mutates one thing about an otherwise aligned pair of sides and asserts
the aligner refuses *with a reason naming that thing* — a refusal that
fires for the wrong reason is not a witness of the property (the
project's rule: a witness must fail for the property, not for its
neighbor).

**What this file does not test.** The adapter's own honesty rules are
``tests/test_paperqa_adapter.py``'s; the six-condition mechanism's
``tests/test_evaluation_harness.py``; the comparison driver's
``tests/test_competitor_comparison.py``. This file watches the machinery
that packages the tasks, plans the run, and aligns the results.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from evaluation import competitor_package as package_module
from evaluation.competitor_align import AlignmentRefusedError, align
from evaluation.competitor_package import (
    PACKAGE_SCHEMA,
    TASK_FACES,
    PackageOutputInsideRepositoryError,
    build_package,
    task_case_files,
    validate_package,
)
from evaluation.competitor_paperqa_run import (
    ArtifactLayout,
    LiveRunNotAuthorizedError,
    build_call_plan,
    require_live_authorization,
)
from evaluation.paperqa_adapter import _expected_statistics

pytestmark = pytest.mark.unit

#: The three task faces' case counts, as the brief's §1 fixes them.
CASE_COUNTS = {
    "numeric-extraction": 11,
    "unsupported-claim-detection": 1,
    "recovery-correctness": 4,
}


#: The fixture names, in the package's own order, for the synthetic bases.
def _fixture_names(package_dir: Path) -> list[str]:
    return sorted(
        Path(name).name.removesuffix(".expected.json")
        for name in task_case_files(package_dir, "numeric-extraction")
    )


def _package(tmp_path: Path) -> Path:
    package_dir = tmp_path / "package"
    build_package(package_dir)
    return package_dir


def _key_versions(package_dir: Path) -> dict[str, str]:
    keys: dict[str, str] = {}
    for face in CASE_COUNTS:
        keys.update(task_case_files(package_dir, face))
    return keys


def _numeric_keys(package_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        Path(name).name.removesuffix(".expected.json"): json.loads(
            (package_dir / "tasks" / name).read_bytes()
        )
        for name in task_case_files(package_dir, "numeric-extraction")
    }


def _write_json_file(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_side(
    side_dir: Path,
    package_dir: Path,
    *,
    label: str,
    model: str,
    numeric_method: str,
    numeric_answer: str,
    abstention_answer: str,
    recovery_surface: str,
) -> None:
    """A synthetic side in the shape the runner scripts write.

    The numeric artifacts are small and honest for their method: exactness
    carries three named cells per case, all true; recall carries the free
    text verbatim and lets the key decide.
    """
    layout = ArtifactLayout(root=side_dir)
    side_dir.mkdir(parents=True, exist_ok=True)
    (side_dir / "run.json").write_text(
        json.dumps(
            {
                "label": label,
                "package_manifest_sha256": _manifest_sha(package_dir),
                "model": model,
                "budget": "synthetic-budget",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (side_dir / "basis.json").write_text(
        json.dumps(
            {
                "label": label,
                "model": model,
                "budget": "synthetic-budget",
                "fixtures": {
                    "names": _fixture_names(package_dir),
                    "versions": {
                        Path(name).name.removesuffix(".expected.json"): digest
                        for name, digest in task_case_files(
                            package_dir, "numeric-extraction"
                        ).items()
                    },
                },
                "verified_capabilities": ["unit", "integration"],
                "limitations": f"{label}'s synthetic limitations sentence",
                "confidence_intervals": "",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    layout.write_key_versions(package_dir)
    for fixture in sorted(_numeric_keys(package_dir)):
        document: dict[str, Any] = {
            "face": "numeric-extraction",
            "case": fixture,
            "fixture": fixture,
            "status": "answered",
            "scoring": numeric_method,
        }
        if numeric_method == "numeric-cell-recall":
            document["answer"] = numeric_answer
        else:
            document["cells"] = [
                {"cell": f"r1:{fixture}:c{i}", "expected": "1", "actual": "1", "ok": True}
                for i in range(3)
            ]
        path = layout.answer_path("numeric-extraction", fixture)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_file(path, document)

    abstention_case = "no_evidence.buffer_ph"
    abstention_document = {
        "face": "unsupported-claim-detection",
        "case": abstention_case,
        "status": "answered",
        "answer": abstention_answer,
        "scoring": "abstention-mechanical",
    }
    path = layout.answer_path("unsupported-claim-detection", abstention_case)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(abstention_document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    surface_document: dict[str, Any] = {"surface": recovery_surface, "scoring": "recovery-surface"}
    if recovery_surface == "present":
        surface_document["faces"] = []
    surface_path = layout.surface_path("recovery-correctness")
    surface_path.parent.mkdir(parents=True, exist_ok=True)
    surface_path.write_text(
        json.dumps(surface_document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if recovery_surface == "present":
        for case in sorted(task_case_files(package_dir, "recovery-correctness")):
            case_name = Path(case).name.removesuffix(".json")
            document = {
                "face": "recovery-correctness",
                "case": case_name,
                "held": True,
                "scoring": "recovery-surface",
            }
            path = layout.answer_path("recovery-correctness", case_name)
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_json_file(path, document)


def _manifest_sha(package_dir: Path) -> str:
    import hashlib

    return hashlib.sha256((package_dir / "manifest.json").read_bytes()).hexdigest()


# -- the package ----------------------------------------------------------


def test_the_package_holds_every_case_of_the_three_faces(tmp_path: Path) -> None:
    """Three faces, eleven plus one plus four cases, and a manifest that is true."""
    package_dir = _package(tmp_path)
    validate_package(package_dir)
    for face, count in CASE_COUNTS.items():
        assert len(task_case_files(package_dir, face)) == count, face


def test_two_builds_are_byte_identical(tmp_path: Path) -> None:
    """The same tree builds the same package: no timestamps, no drift.

    The builds are deliberately separated by longer than a zip timestamp's
    two-second tick: the spreadsheets are generated, and a shorter gap
    once let two builds share a tick and pass by luck. The gap is what
    makes the identity a measurement and not a coincidence.
    """
    first = _package(tmp_path / "a")
    time.sleep(3)
    second = _package(tmp_path / "b")
    first_files = {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files


def test_a_package_inside_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runner input lives outside the tree, and the builder enforces it."""
    fake_root = tmp_path / "fake-repo"
    fake_root.mkdir()
    monkeypatch.setattr(package_module, "find_repository_root", lambda _start: fake_root)
    with pytest.raises(PackageOutputInsideRepositoryError):
        build_package(fake_root / "inside")


def test_the_numeric_questions_are_the_adapter_template_of_the_keys(tmp_path: Path) -> None:
    """The packaged question is the adapter's, byte for byte, from the packaged key."""
    from evaluation.paperqa_adapter import question_for

    package_dir = _package(tmp_path)
    for fixture, key in _numeric_keys(package_dir).items():
        question_file = (
            package_dir / "tasks" / "numeric-extraction" / "questions" / f"{fixture}.question.txt"
        )
        assert question_file.read_bytes() == question_for(key).encode()


def test_the_packaged_spreadsheets_still_render_as_their_source_csv(
    tmp_path: Path,
) -> None:
    """The deterministic repack changes the stamping, never the cells.

    The spreadsheets in the package are repacked so their bytes are
    stable; this witness holds the adapter's own ruling — a spreadsheet's
    rendering is its source CSV's text — against the *repacked* bytes, so
    the stability fix cannot quietly break the task.
    """
    from evaluation.paperqa_adapter import _render_spreadsheet, render_fixture

    package_dir = _package(tmp_path)
    sources = {"numeric.xlsx": "basic.csv", "holes.xlsx": "holes.csv"}
    for fixture, source_csv in sources.items():
        packaged = (
            package_dir / "tasks" / "numeric-extraction" / "fixtures" / fixture
        ).read_bytes()
        assert _render_spreadsheet(packaged) == render_fixture(source_csv), fixture


def test_the_recovery_statements_carry_the_specification_windows(tmp_path: Path) -> None:
    """The four crash windows are the contract's four, named and rowed."""
    package_dir = _package(tmp_path)
    scenarios = package_dir / "tasks" / "recovery-correctness" / "scenarios"
    names = sorted(path.stem for path in scenarios.glob("*.json"))
    assert names == [
        "after_attempted_before_write",
        "after_confirm_before_notify",
        "after_write_before_confirm",
        "before_attempted_commit",
    ]


# -- the call plan and the live gate --------------------------------------


def test_the_call_plan_covers_the_package_once_per_document_qa_case(
    tmp_path: Path,
) -> None:
    """Eleven plus one cases at one call each, the recovery face zero."""
    package_dir = _package(tmp_path)
    plan = build_call_plan(package_dir)
    assert tuple(planned.face for planned in plan.faces) == TASK_FACES
    assert [len(planned.cases) for planned in plan.faces] == [11, 1, 0]
    assert plan.provider_calls_min == 12
    assert plan.faces[2].surface == "absent"


def test_the_live_gate_refuses_without_the_owner_approval_file(tmp_path: Path) -> None:
    """Live mode's first act is the refusal: nothing imported, nothing spent."""
    with pytest.raises(LiveRunNotAuthorizedError, match="approval file"):
        require_live_authorization(tmp_path / "absent.json")


def test_the_live_gate_refuses_an_approval_that_declares_nothing(tmp_path: Path) -> None:
    """An approval file without a budget or an approver is not an approval."""
    approval = tmp_path / "approval.json"
    _write_json_file(approval, {"budget": "", "approved_by": ""})
    with pytest.raises(LiveRunNotAuthorizedError, match="does not declare"):
        require_live_authorization(approval)


def test_the_live_gate_reads_a_complete_approval(tmp_path: Path) -> None:
    """A complete approval carries the budget, the approver, and the model."""
    approval = tmp_path / "approval.json"
    approval.write_text(
        json.dumps({"budget": "b-1", "approved_by": "owner", "model": "m-1"}),
        encoding="utf-8",
    )
    assert require_live_authorization(approval)["budget"] == "b-1"


# -- the aligner's happy path ----------------------------------------------


def _aligned_pair(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Two synthetic sides that align cleanly, verified before any mutation.

    Every refusal test mutates this pair; the verification here is what
    makes the refusal mean something — the witness fails for the property,
    not because the fixture was already broken.
    """
    package_dir = _package(tmp_path / "pkg")
    our_dir = tmp_path / "ours"
    competitor_dir = tmp_path / "competitor"
    _write_side(
        our_dir,
        package_dir,
        label="our run",
        model="test-model",
        numeric_method="numeric-cell-exactness",
        numeric_answer="",
        abstention_answer="the material does not state the pH of the wash buffer",
        recovery_surface="present",
    )
    _write_side(
        competitor_dir,
        package_dir,
        label="paper-qa",
        model="test-model",
        numeric_method="numeric-cell-recall",
        numeric_answer="",
        abstention_answer="The pH of the wash buffer was 50.0.",
        recovery_surface="absent",
    )
    baseline = align(package_dir, our_dir, competitor_dir)
    assert baseline.comparison.comparable, baseline.comparison.reasons
    return package_dir, our_dir, competitor_dir


def test_an_aligned_pair_is_comparable_with_the_three_faces_scored(
    tmp_path: Path,
) -> None:
    """The whole chain: two synthetic sides align, all six conditions met."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    outcome = align(package_dir, our_dir, competitor_dir)
    assert outcome.comparison.comparable, outcome.comparison.reasons
    assert outcome.our_metrics["numeric-extraction-exactness"] == {
        "numerator": 33,
        "denominator": 33,
    }
    assert outcome.our_metrics["unsupported-claim-detection"] == {
        "numerator": 1,
        "denominator": 1,
    }
    assert outcome.our_metrics["recovery-correctness"] == {"numerator": 4, "denominator": 4}
    expected_recall_denominator = sum(
        len(_expected_statistics(key)) for key in _numeric_keys(package_dir).values()
    )
    assert outcome.competitor_metrics["numeric-extraction-recall"] == {
        "numerator": 0,
        "denominator": expected_recall_denominator,
    }
    assert outcome.competitor_metrics["unsupported-claim-detection"] == {
        "numerator": 0,
        "denominator": 1,
    }
    assert outcome.competitor_metrics["recovery-correctness"] == {
        "numerator": 0,
        "denominator": 4,
    }


def test_the_scope_facts_pair_but_the_task_one_denominators_do_not(tmp_path: Path) -> None:
    """Tasks 2 and 3 measure the same thing on both sides and pair; task 1 does not."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    outcome = align(package_dir, our_dir, competitor_dir)
    document = outcome.as_document()
    paired = {row["metric"] for row in document["pairs"]}
    assert "unsupported-claim-detection" in paired
    assert "recovery-correctness" in paired
    assert "numeric-extraction-recall" not in paired
    assert "numeric-extraction-exactness" not in paired


def test_a_key_addressing_no_cells_scores_zero_over_zero(tmp_path: Path) -> None:
    """The empty fixture's key declares no cells; its exactness score is 0 over 0.

    The key's own note says the file produces no cells at all — its
    statistics are null — so an exactness artifact carrying an empty cells
    list is the honest reading of that key, and the recall rule already
    scores the same key 0 over 0. Refusing it would refuse the corpus.
    """
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    artifact = our_dir / "answers" / "numeric-extraction" / "empty.csv.json"
    document = json.loads(artifact.read_text(encoding="utf-8"))
    document["cells"] = []
    artifact.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outcome = align(package_dir, our_dir, competitor_dir)
    assert outcome.comparison.comparable, outcome.comparison.reasons
    exactness = outcome.our_metrics["numeric-extraction-exactness"]
    assert exactness["numerator"] == 30
    assert exactness["denominator"] == 30


def test_an_exactness_artifact_without_a_cells_list_is_still_refused(
    tmp_path: Path,
) -> None:
    """A missing cells list is not the same fact as an empty one."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    artifact = our_dir / "answers" / "numeric-extraction" / "basic.csv.json"
    document = json.loads(artifact.read_text(encoding="utf-8"))
    del document["cells"]
    artifact.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(AlignmentRefusedError):
        align(package_dir, our_dir, competitor_dir)


# -- the aligner's refusals, one mutation each -----------------------------


def _refusal_reasons(package_dir: Path, our_dir: Path, competitor_dir: Path) -> tuple[str, ...]:
    with pytest.raises(AlignmentRefusedError) as raised:
        align(package_dir, our_dir, competitor_dir)
    return raised.value.reasons


def test_a_missing_task_face_refuses_the_alignment(tmp_path: Path) -> None:
    """A side that drops a case is refused, and the reason names the case."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    (
        competitor_dir / "answers" / "unsupported-claim-detection" / "no_evidence.buffer_ph.json"
    ).unlink()
    reasons = _refusal_reasons(package_dir, our_dir, competitor_dir)
    assert any("missing case no_evidence.buffer_ph" in reason for reason in reasons), reasons


def test_a_misfiled_artifact_refuses_the_alignment(tmp_path: Path) -> None:
    """An artifact whose declared case is not its file name is a misplaced cell."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    answers = competitor_dir / "answers" / "numeric-extraction"
    basic = answers / "basic.csv.json"
    document = json.loads(basic.read_text(encoding="utf-8"))
    (answers / "declared.csv.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    basic.unlink()
    reasons = _refusal_reasons(package_dir, our_dir, competitor_dir)
    assert any("filed under a name it does not declare" in reason for reason in reasons), reasons


def test_a_key_pin_that_does_not_match_the_package_refuses_the_alignment(
    tmp_path: Path,
) -> None:
    """A side that ran against different keys ran a different corpus."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    pins_path = competitor_dir / "key-versions.json"
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    some_key = sorted(pins)[0]
    pins[some_key] = "0" * 64
    _write_json_file(pins_path, pins)
    reasons = _refusal_reasons(package_dir, our_dir, competitor_dir)
    assert any(some_key in reason and "pinned" in reason for reason in reasons), reasons


def test_a_scoring_method_outside_the_table_refuses_the_alignment(
    tmp_path: Path,
) -> None:
    """The method table is closed: an invented method is a refusal, not a default."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    artifact_path = competitor_dir / "answers" / "numeric-extraction" / "basic.csv.json"
    document = json.loads(artifact_path.read_text(encoding="utf-8"))
    document["scoring"] = "invented-method"
    artifact_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    reasons = _refusal_reasons(package_dir, our_dir, competitor_dir)
    assert any("invented-method" in reason for reason in reasons), reasons


def test_a_run_record_naming_another_package_refuses_the_alignment(
    tmp_path: Path,
) -> None:
    """A side must name the package it ran, by the manifest hash."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    run_path = competitor_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["package_manifest_sha256"] = "0" * 64
    _write_json_file(run_path, run)
    reasons = _refusal_reasons(package_dir, our_dir, competitor_dir)
    assert any("run record names package manifest" in reason for reason in reasons), reasons


def test_an_answer_with_no_forbidden_value_honours_the_abstention(tmp_path: Path) -> None:
    """The mechanical rule scores the honest abstention 1 — and it is the key's values it checks."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    artifact_path = (
        competitor_dir / "answers" / "unsupported-claim-detection" / "no_evidence.buffer_ph.json"
    )
    document = json.loads(artifact_path.read_text(encoding="utf-8"))
    document["answer"] = "the material reports no pH for the wash buffer"
    artifact_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    outcome = align(package_dir, our_dir, competitor_dir)
    assert outcome.competitor_metrics["unsupported-claim-detection"] == {
        "numerator": 1,
        "denominator": 1,
    }


def test_the_alignment_document_carries_the_package_schema(tmp_path: Path) -> None:
    """The comparison document declares its schema, like every record here."""
    package_dir, our_dir, competitor_dir = _aligned_pair(tmp_path)
    outcome = align(package_dir, our_dir, competitor_dir)
    assert outcome.as_document()["schema"] == PACKAGE_SCHEMA
