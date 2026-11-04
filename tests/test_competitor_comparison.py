"""LC-P2-18's comparison driver, watched.

**What this file watches.** ``tests/evaluation/competitor_run.py`` builds
the two sides of the competitor comparison, asks the six conditions, and
renders a report. The witnesses here hold the properties the brief's
acceptance clauses state:

* a dry run produces a report in which all six conditions are met, and
  the record says **zero provider calls**, which side is a stub, and an
  empty model on both sides;
* the rendered report names no verdict — it is checked against
  :func:`~tests.evaluation.report.ranking_pattern`, the same vocabulary
  the harness's own comparison section is checked against;
* a real run without a budget ceiling, our side's outbound-consent
  record, or the owner's approval for the competitor run is refused
  before either side is built;
* even a fully approved real run is refused, because our side has no
  model-declaring frozen run — the structural fact brief §1 states;
* the frozen baseline is not carried forward when its answer-key pins no
  longer describe the tree.

**What this file does not test.** The adapter's own honesty rules are
watched by ``tests/test_paperqa_adapter.py``, and the six-condition
mechanism by ``tests/test_evaluation_harness.py``. This file watches the
driver that joins them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from evaluation.competitor_run import (
    BASELINE_PATH,
    DRY_RUN,
    REAL,
    STUB_ANSWER,
    STUB_METRIC,
    FrozenBaselineMovedError,
    RealRunRefusedError,
    frozen_labcairn_side,
    render_report,
    run_comparison,
    stub_competitor_side,
)
from evaluation.corpus import CORPUS_FIXTURES
from evaluation.report import ranking_pattern

pytestmark = pytest.mark.unit

#: The six conditions, in the order the protocol states them.
CONDITIONS = (
    "matched_task",
    "matched_task_versions",
    "matched_model",
    "matched_budget",
    "verified_capabilities",
    "documented_limits",
)


def test_the_dry_run_meets_all_six_conditions(repo_root: Path) -> None:
    """The dry run's whole point: the six-row machinery runs and all six hold."""
    run = run_comparison(DRY_RUN, repo_root)
    assert run.outcome.comparable, run.outcome.reasons
    assert run.outcome.reasons == ()
    assert tuple(check.name for check in run.outcome.conditions) == CONDITIONS
    assert all(check.met for check in run.outcome.conditions), [
        check.detail for check in run.outcome.conditions if not check.met
    ]
    assert run.provider_calls == 0
    assert len(run.our_side.basis.fixture_labels) == len(CORPUS_FIXTURES)


def test_the_record_declares_zero_provider_calls_and_which_side_is_a_stub(
    repo_root: Path,
) -> None:
    """The honest labels the brief requires are in the record, not only in prose."""
    record = run_comparison(DRY_RUN, repo_root).record()
    assert record["mode"] == "dry-run"
    assert record["provider_calls"] == 0
    assert record["sides"]["ours"]["provider_calls"] == 0
    assert record["sides"]["competitor"]["provider_calls"] == 0
    assert record["sides"]["ours"]["stub"] is False
    assert record["sides"]["competitor"]["stub"] is True
    assert record["sides"]["ours"]["model"] == ""
    assert record["sides"]["competitor"]["model"] == ""
    assert record["sides"]["ours"]["budget"] == ""
    assert record["sides"]["competitor"]["budget"] == ""
    assert "frozen" in record["sides"]["ours"]["source"]
    assert "stub" in record["sides"]["competitor"]["source"]


def test_the_report_renders_the_six_conditions_and_no_verdict(
    repo_root: Path,
) -> None:
    """The report repeats the six rows and contains no verdict-carrying word."""
    run = run_comparison(DRY_RUN, repo_root)
    markdown = render_report(run)
    assert ranking_pattern().search(markdown) is None
    for check in run.outcome.conditions:
        assert check.name in markdown
    assert "The six conditions are met" in markdown


def test_the_stub_side_goes_through_the_adapter_once_per_fixture() -> None:
    """The stub's answer is captured untouched, and every fixture is a case."""
    side = stub_competitor_side()
    assert len(side.artifacts) == len(CORPUS_FIXTURES)
    assert all(artifact["status"] == "answered" for artifact in side.artifacts)
    assert [artifact["answer"] for artifact in side.artifacts] == [STUB_ANSWER] * len(
        CORPUS_FIXTURES
    )
    assert side.basis.model == ""
    assert side.basis.budget == ""


def test_the_two_sides_share_no_metric_name_so_no_pair_is_printed(
    repo_root: Path,
) -> None:
    """Two denominators under one name would not be one measurement."""
    run = run_comparison(DRY_RUN, repo_root)
    assert STUB_METRIC in run.competitor_side.metrics
    assert STUB_METRIC not in run.our_side.metrics
    assert "numeric-extraction-exactness" in run.our_side.metrics
    assert run.metric_pairs == ()
    assert "No metric name is measured on both sides" in render_report(run)


def test_a_real_run_without_a_budget_ceiling_is_refused(repo_root: Path) -> None:
    """The budget is the owner's decision, and the driver does not invent it."""
    with pytest.raises(RealRunRefusedError) as caught:
        run_comparison(REAL, repo_root)
    assert any("budget" in reason for reason in caught.value.reasons)


def test_a_real_run_without_our_consent_is_refused(repo_root: Path, tmp_path: Path) -> None:
    """No run starts around the outbound-consent bridge."""
    approval = tmp_path / "competitor-approval.txt"
    approval.write_text("approved\n", encoding="utf-8")
    with pytest.raises(RealRunRefusedError) as caught:
        run_comparison(
            REAL,
            repo_root,
            budget="USD 10",
            competitor_approval=approval,
        )
    assert any("consent" in reason for reason in caught.value.reasons)


def test_a_real_run_without_the_competitor_approval_is_refused(
    repo_root: Path, tmp_path: Path
) -> None:
    """The final competitor list is the owner's decision."""
    consent = tmp_path / "our-consent.txt"
    consent.write_text("consented\n", encoding="utf-8")
    with pytest.raises(RealRunRefusedError) as caught:
        run_comparison(
            REAL,
            repo_root,
            budget="USD 10",
            our_consent=consent,
        )
    assert any("approval" in reason for reason in caught.value.reasons)


def test_a_fully_approved_real_run_is_refused_for_the_structural_reason(
    repo_root: Path, tmp_path: Path
) -> None:
    """With all three approvals the refusal is the one that cannot be bought.

    Brief §1: the frozen offline baseline cannot be our side of a real
    comparison, because it declares no model and a real competitor does. A
    driver that ran anyway would be fabricating our side.
    """
    consent = tmp_path / "our-consent.txt"
    consent.write_text("consented\n", encoding="utf-8")
    approval = tmp_path / "competitor-approval.txt"
    approval.write_text("approved\n", encoding="utf-8")
    with pytest.raises(RealRunRefusedError) as caught:
        run_comparison(
            REAL,
            repo_root,
            budget="USD 10",
            our_consent=consent,
            competitor_approval=approval,
        )
    assert len(caught.value.reasons) == 1
    assert "model" in caught.value.reasons[0]
    assert "frozen basis" in caught.value.reasons[0]


def test_the_driver_names_no_provider_adapter(repo_root: Path) -> None:
    """There is no second path around the outbound-consent bridge."""
    source = (repo_root / "tests" / "evaluation" / "competitor_run.py").read_text(encoding="utf-8")
    assert "PydanticAiModelProvider" not in source
    assert "labcairn.providers" not in source


def test_the_frozen_side_refuses_when_an_answer_key_pin_no_longer_matches(
    repo_root: Path, tmp_path: Path
) -> None:
    """A frozen number whose anchor moved is not carried forward."""
    document: dict[str, Any] = json.loads((repo_root / BASELINE_PATH).read_text(encoding="utf-8"))
    fixture = CORPUS_FIXTURES[0]
    document["fixtures"]["versions"][fixture] = "0" * 64
    moved = tmp_path / "baseline.json"
    moved.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(FrozenBaselineMovedError) as caught:
        frozen_labcairn_side(tmp_path, baseline_path=moved)
    assert fixture in caught.value.message


def _command_environment(repo_root: Path) -> dict[str, str]:
    """An environment in which the script imports this tree, not another."""
    environment = dict(os.environ)
    paths = [str(repo_root / "src"), str(repo_root / "tests")]
    existing = environment.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


def test_the_command_line_writes_the_report_and_the_record(repo_root: Path, tmp_path: Path) -> None:
    """The entry point runs a dry run and leaves both artifacts behind."""
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "run_competitor_comparison.py"),
            "--output",
            str(output),
        ],
        cwd=repo_root,
        env=_command_environment(repo_root),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    report = (output / "comparison-report.md").read_text(encoding="utf-8")
    record = json.loads((output / "comparison-record.json").read_text(encoding="utf-8"))
    assert record["provider_calls"] == 0
    assert record["comparable"] is True
    assert ranking_pattern().search(report) is None


def test_the_command_line_refuses_a_real_run_without_a_budget(
    repo_root: Path, tmp_path: Path
) -> None:
    """The refusal is before anything is written, and its status is 2."""
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "run_competitor_comparison.py"),
            "--mode",
            "real",
            "--output",
            str(output),
        ],
        cwd=repo_root,
        env=_command_environment(repo_root),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 2
    assert "budget" in completed.stderr
    assert not output.exists()
