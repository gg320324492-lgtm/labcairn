"""The frozen Phase 1 baseline, watched.

**What this file watches.** ``docs/acceptance/LC-P2-00-baseline.json`` is
the frozen Phase 1 baseline: the numbers the evaluation harness measured on
the tree at the commit the document names, and the basis a later comparison
run has to match before its numbers may be printed beside these. A baseline
that nobody watches is a document that can be edited in place — a commit
swapped for one the numbers never belonged to, a fixture version carried
past the answer key it was measured against, a capability list quietly
extended — and every later *"measured capability gain"* would be measured
against a denominator that moved without anyone seeing it move.

So four properties are watched here, each for the failure it is shaped
against:

* **The document loads.** ``load_baseline`` reads it, and the structure the
  comparison needs is really there: a basis that declares no model (the
  offline run's own declaration), a non-empty capability list, a non-empty
  limitations line, and metrics whose every entry carries an int numerator
  and a positive int denominator.
* **A run on this tree compares.** The run side of the comparison is
  rebuilt the way the harness builds it — the committed answer keys hashed
  exactly as ``cli._run_basis`` hashes them, the empty model and budget the
  offline run declares, the capabilities that run reported — and
  :func:`evaluation.comparison.assess` accepts it **on all six
  conditions**. This is the property the work order names, and it doubles
  as the anchor: edit an answer key without re-freezing the baseline and
  the versions stop matching, so the comparison refuses and this test
  fails with it.
* **A doctored basis is refused.** Each of the six conditions, broken one
  at a time, makes ``assess`` return a refusal with a reason. A refusal
  that cannot be produced is a refusal that will not fire when it matters;
  this is the work order's *"the refusal witnesses stay red against a
  doctored basis"*.
* **The commit is what the numbers belong to.** The document's run block
  names a commit; the answer keys of that commit, read out of git itself,
  hash to exactly the versions the document declares. A commit swapped for
  one the numbers never belonged to fails here, before any comparison can
  be drawn against it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Final

import pytest
from evaluation.comparison import ComparisonBasis, assess, load_baseline
from evaluation.corpus import CORPUS_FIXTURES
from evaluation.manifest import ALL_CLASS_KEYS

_ROOT: Final = Path(__file__).resolve().parent.parent
_BASELINE: Final = _ROOT / "docs" / "acceptance" / "LC-P2-00-baseline.json"

#: Where an answer key lives, relative to the repository root — the same
#: place the harness's ``_run_basis`` reads it from.
_KEY_PATH: Final = "tests/fixtures/analysis/{fixture}.expected.json"

#: The class the protocol requires and this machine cannot run: no provider
#: credential is configured, and a mock-only success is insufficient. The
#: frozen baseline records the class as NOT RUN rather than as a pass.
_REAL_MODEL_SMOKE: Final = "real_model_smoke"


def _document() -> dict[str, Any]:
    """The baseline document as JSON, run block included."""
    document: dict[str, Any] = json.loads(_BASELINE.read_text(encoding="utf-8"))
    return document


def _answer_key(fixture: str) -> Path:
    return _ROOT / _KEY_PATH.format(fixture=fixture)


def _tree_versions() -> dict[str, str]:
    """The answer keys of **this** tree, hashed the way the harness hashes them."""
    versions = {
        fixture: hashlib.sha256(_answer_key(fixture).read_bytes()).hexdigest()
        for fixture in CORPUS_FIXTURES
        if _answer_key(fixture).is_file()
    }
    assert set(versions) == set(CORPUS_FIXTURES), (
        "the corpus declares fixtures whose answer key is not in the tree"
    )
    return versions


def _run_side_basis() -> ComparisonBasis:
    """The run side of the comparison, rebuilt the way the harness builds it.

    The harness's own ``cli._run_basis`` takes the class results of a live
    run; the capabilities it reported are read out of the document's run
    block, which records what that run said about itself. Everything else
    is rebuilt from **this** tree: the committed answer keys, the empty
    model and budget the offline run declares.
    """
    run = _document()["run"]
    return ComparisonBasis(
        label="this run (rebuilt)",
        fixture_labels=CORPUS_FIXTURES,
        fixture_versions=_tree_versions(),
        model="",
        budget="",
        verified_capabilities=tuple(run["verified_capabilities"]),
        limitations=run["limitations"],
    )


def _git(*arguments: str) -> bytes:
    """The raw bytes a git command prints, from this repository."""
    completed = subprocess.run(
        ["git", *arguments],
        cwd=str(_ROOT),
        capture_output=True,
        check=True,
    )
    return completed.stdout


def test_the_baseline_document_loads() -> None:
    """The document the comparisons will read is readable and complete."""
    baseline = load_baseline(_BASELINE)
    assert baseline.basis.label
    # The offline run declares no model: the harness's FakeProvider is not
    # a declared model, version and parameter set, and the document says so
    # rather than naming one.
    assert baseline.basis.model == ""
    assert baseline.basis.verified_capabilities
    assert baseline.basis.limitations or baseline.basis.confidence_intervals
    assert set(baseline.basis.fixture_versions) == set(CORPUS_FIXTURES)
    assert baseline.metrics
    for key, (numerator, denominator) in baseline.metrics.items():
        assert isinstance(numerator, int) and numerator >= 0, key
        assert isinstance(denominator, int) and denominator > 0, key


def test_a_run_on_this_tree_compares_on_all_six_conditions() -> None:
    """A run built the way the harness builds one is comparable, no reasons."""
    baseline = load_baseline(_BASELINE)
    outcome = assess(_run_side_basis(), baseline.basis)
    assert outcome.comparable is True
    assert outcome.reasons == ()


#: Each of the four *matching* conditions, broken on the **run** side: a run
#: that declares a different model, budget, task set or task version is not
#: like-for-like, and the comparison must refuse it.
_DOCTORED_RUNS: Final = [
    pytest.param({"model": "a-model-the-run-did-not-declare"}, id="model"),
    pytest.param({"budget": "a-budget-the-run-did-not-declare"}, id="budget"),
    pytest.param({"fixture_labels": CORPUS_FIXTURES[:-1]}, id="tasks"),
    pytest.param(
        {"fixture_versions": {**_tree_versions(), "basic.csv": "0" * 64}},
        id="task-versions",
    ),
]

#: Each of the two *declaration* conditions, broken on the **baseline**
#: side: a baseline that declares no capabilities, or neither limits nor
#: intervals, is a baseline whose numbers cannot be read with any stated
#: uncertainty, and the comparison must refuse it.
_DOCTORED_BASELINES: Final = [
    pytest.param({"verified_capabilities": ()}, id="capabilities"),
    pytest.param(
        {"limitations": "", "confidence_intervals": ""},
        id="documented-limits",
    ),
]


@pytest.mark.parametrize(("doctored",), _DOCTORED_RUNS)
def test_a_doctored_run_is_refused(doctored: dict[str, Any]) -> None:
    """A matching condition, broken on the run side, makes the comparison refuse."""
    baseline = load_baseline(_BASELINE)
    run_side = dataclasses.replace(_run_side_basis(), **doctored)
    outcome = assess(run_side, baseline.basis)
    assert outcome.comparable is False
    assert outcome.reasons


@pytest.mark.parametrize(("doctored",), _DOCTORED_BASELINES)
def test_a_doctored_baseline_is_refused(doctored: dict[str, Any]) -> None:
    """A declaration condition, broken on the baseline side, makes it refuse."""
    baseline = load_baseline(_BASELINE)
    baseline_basis = dataclasses.replace(baseline.basis, **doctored)
    outcome = assess(_run_side_basis(), baseline_basis)
    assert outcome.comparable is False
    assert outcome.reasons


def test_the_run_block_names_the_commit_the_numbers_belong_to() -> None:
    """The commit the document names carries the answer keys it declares."""
    commit = _document()["run"]["commit"]
    assert len(commit) == 40
    assert all(character in "0123456789abcdef" for character in commit)
    _git("cat-file", "-e", f"{commit}^{{commit}}")
    for fixture, recorded in _document()["fixtures"]["versions"].items():
        blob = _git("show", f"{commit}:{_KEY_PATH.format(fixture=fixture)}")
        assert hashlib.sha256(blob).hexdigest() == recorded, fixture


def test_the_run_block_reports_the_offline_run_it_was() -> None:
    """The run block says what the run actually was, and what was not run."""
    run = _document()["run"]
    assert set(run["verified_capabilities"]) < set(ALL_CLASS_KEYS)
    assert _REAL_MODEL_SMOKE not in run["verified_capabilities"]
    assert any(entry["class"] == _REAL_MODEL_SMOKE for entry in run["not_run"])
    assert run["exit_code"] == 2
