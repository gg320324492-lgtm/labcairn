"""LC-P2-18's comparison driver: two sides, six conditions, one report.

**What this module is.** The brief
(``docs/plans/LC-P2-18-competitor-baseline-brief.md``) says a side of the
comparison is *one basis document plus the run's raw artifacts*, and that
the six conditions in ``comparison.py`` decide whether two sides may be
printed together. This module builds the two sides for a **dry run**,
asks :func:`~tests.evaluation.comparison.assess` the six-condition
question, and renders the answer — pairs, never a verdict.

**What the dry run can honestly be.**

* **Our side is the frozen Phase 1 baseline**, read from
  ``docs/acceptance/LC-P2-00-baseline.json``. Its numbers came from the
  deterministic ``FakeProvider``; its own ``limitations`` sentence says
  those numbers measure the repository's tests and not a model's
  behaviour. The dry run does not re-measure them, and it says so.
* **The competitor side is a deterministic stub** driven through
  :mod:`tests.evaluation.paperqa_adapter`. The stub answers every case
  with one sentence that computes nothing. That exercises the adapter's
  wire — render, ask, capture, score — and produces a recall, but the
  recall is a wiring measurement, not a capability measurement.

Both sides declare ``model=""`` and ``budget=""``, so the six conditions
are met. **That pairing does not carry to a real run**: a real competitor
declares a model, and brief §1 states the structural fact that the frozen
offline baseline cannot be our side of that comparison. The disclosures
the report prints say this in the report's own words, and
``tests/test_competitor_comparison.py`` watches them.

**No metric is printed as a pair.** Our side counts exact cells; the
stub side counts the key's expected statistics recalled by the stub's
text. Two different denominators under one name would be one number
pretending to be another, so :func:`~tests.evaluation.comparison.pairs`
finds no shared name and the report says why.

**The real mode refuses.** It needs a budget ceiling, our side's
outbound-consent record and the owner's approval for the competitor run;
without any of them it raises :class:`RealRunRefusedError` before a side is
built. With all three it **still** refuses, for the structural reason
above: this driver has no model-declaring frozen run to put on our side,
and inventing one would be the fabrication the brief exists to prevent.
Nothing here constructs a provider, so there is no path around the
outbound-consent bridge.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from analysis_fixtures import expected_path, load_expected

from .comparison import ComparisonBasis, assess, load_baseline, pairs
from .corpus import CORPUS_FIXTURES
from .model import ComparisonOutcome
from .paperqa_adapter import run_case, score_artifact
from .report import ranking_pattern

#: The two modes the driver distinguishes.
DRY_RUN: Final = "dry-run"
REAL: Final = "real"
MODES: Final = (DRY_RUN, REAL)

#: Where the frozen Phase 1 baseline lives, relative to the repository root.
BASELINE_PATH: Final = Path("docs") / "acceptance" / "LC-P2-00-baseline.json"

#: The sentence the stub answers every case with. It carries no digits on
#: purpose: a dry run may not accidentally look like it computed something.
STUB_ANSWER: Final = "STUB-COMPETITOR-ANSWER: no model was called; this response computes nothing."

#: The stub side's metric name. It is deliberately **not** the baseline's
#: ``numeric-extraction-exactness``: the two count different things (cells
#: against expected statistics), and a shared name would put two
#: denominators under one label.
STUB_METRIC: Final = "numeric-extraction-recall"


class FrozenBaselineMovedError(RuntimeError):
    """The frozen baseline no longer pins the answer keys in this tree.

    A baseline's version labels are content pins. When the bytes they pin
    change, the frozen numbers are not a measurement of this tree any
    more, and carrying them forward would be the value the project's rule
    forbids carrying: a number whose anchor has moved.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RealRunRefusedError(RuntimeError):
    """A real comparison was requested without what it has to bring."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class RankingLanguageError(RuntimeError):
    """A rendered report carried a verdict-carrying word.

    The protocol forbids a superiority claim without like-for-like matched
    tasks, and the comparison's vocabulary rule is what stops one. The
    renderer checks its own output against
    :func:`~tests.evaluation.report.ranking_pattern`; a report that says
    "better" anywhere is a report that has claimed something.
    """


@dataclass(frozen=True, slots=True)
class SideArtifacts:
    """One side of the comparison: what it says about itself, and its numbers."""

    #: The basis the six conditions are checked against.
    basis: ComparisonBasis
    #: The metric numbers, as numerator over denominator.
    metrics: Mapping[str, tuple[int, int]]
    #: Where the numbers came from, in words a reader can check.
    source: str
    #: Whether a deterministic stub, rather than a system, produced the side.
    stub: bool
    #: Provider calls this run made for this side. Always zero in a dry run.
    provider_calls: int = 0
    #: The raw artifacts the side produced, when it produced any.
    artifacts: tuple[Mapping[str, Any], ...] = ()
    #: Anything else the side wants recorded.
    notes: tuple[str, ...] = field(default=())

    def record(self) -> dict[str, Any]:
        """The side as a JSON-serialisable record."""
        return {
            "label": self.basis.label,
            "source": self.source,
            "stub": self.stub,
            "provider_calls": self.provider_calls,
            "model": self.basis.model,
            "budget": self.basis.budget,
            "fixtures": list(self.basis.fixture_labels),
            "versions": dict(self.basis.fixture_versions),
            "metrics": {
                name: [numerator, denominator]
                for name, (numerator, denominator) in sorted(self.metrics.items())
            },
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    """A dry run's two sides, the six-condition outcome, and its disclosures."""

    #: ``dry-run`` or ``real``. Only ``dry-run`` reaches this record today.
    mode: str
    #: Our side.
    our_side: SideArtifacts
    #: The competitor side.
    competitor_side: SideArtifacts
    #: What the six conditions decided.
    outcome: ComparisonOutcome
    #: The metric pairs a comparable comparison prints. Empty when the two
    #: sides share no metric name.
    metric_pairs: tuple[tuple[str, str], ...]
    #: The honesty statements the report carries, in the report's words.
    disclosures: tuple[str, ...]

    @property
    def provider_calls(self) -> int:
        """Provider calls this run made, both sides together."""
        return self.our_side.provider_calls + self.competitor_side.provider_calls

    def record(self) -> dict[str, Any]:
        """The run as a JSON-serialisable record."""
        return {
            "mode": self.mode,
            "provider_calls": self.provider_calls,
            "comparable": self.outcome.comparable,
            "reasons": list(self.outcome.reasons),
            "conditions": [
                {"name": check.name, "met": check.met, "detail": check.detail}
                for check in self.outcome.conditions
            ],
            "metric_pairs": [list(pair) for pair in self.metric_pairs],
            "sides": {
                "ours": self.our_side.record(),
                "competitor": self.competitor_side.record(),
            },
            "disclosures": list(self.disclosures),
        }


def _answer_key_versions() -> dict[str, str]:
    """The content pin of every fixture's committed answer key.

    The same computation ``tests/evaluation/cli.py`` makes for a run
    basis: ``sha256`` of the key's bytes. Two sides "ran the same tasks"
    only when these labels are equal, so the label is a content pin and
    not a string.
    """
    versions: dict[str, str] = {}
    for fixture in CORPUS_FIXTURES:
        path = expected_path(fixture)
        if not path.is_file():
            raise FrozenBaselineMovedError(
                f"the answer key for {fixture!r} is missing at {path}; "
                "a comparison cannot pin a task whose key is not in the tree"
            )
        versions[fixture] = hashlib.sha256(path.read_bytes()).hexdigest()
    return versions


def frozen_labcairn_side(repo_root: Path, *, baseline_path: Path | None = None) -> SideArtifacts:
    """Our side, read from the frozen Phase 1 baseline.

    The numbers are **read, not re-measured**. That is the honest reading
    of "our side's numbers come from the frozen baseline": a value that
    can change is re-measured, but a baseline is by definition frozen, so
    the dry run's job is to check that its pins still describe this tree
    and then report its numbers as the baseline's.

    :raises FrozenBaselineMovedError: when the document's fixture labels or
        version pins no longer match the committed corpus and answer keys.
    """
    document_path = baseline_path or repo_root / BASELINE_PATH
    document = load_baseline(document_path)
    frozen_labels = tuple(document.basis.fixture_labels)
    if frozen_labels != CORPUS_FIXTURES:
        raise FrozenBaselineMovedError(
            "the frozen baseline covers "
            f"{list(frozen_labels)} but the tree's corpus is "
            f"{list(CORPUS_FIXTURES)}; the frozen numbers are not a "
            "measurement of these tasks"
        )
    current_versions = _answer_key_versions()
    frozen_versions = dict(document.basis.fixture_versions)
    if frozen_versions != current_versions:
        changed = sorted(
            fixture
            for fixture in CORPUS_FIXTURES
            if frozen_versions.get(fixture) != current_versions.get(fixture)
        )
        raise FrozenBaselineMovedError(
            "the frozen baseline pins different answer-key versions for "
            f"{changed}; the baseline has to be re-frozen before its numbers "
            "are printed beside another side"
        )
    return SideArtifacts(
        basis=document.basis,
        metrics=document.metrics,
        source=(
            f"the frozen Phase 1 baseline at {document_path.name}, read in "
            "place; its numbers came from the deterministic FakeProvider and "
            "were not re-measured"
        ),
        stub=False,
        notes=(
            "the model is empty by the baseline's own record: the offline "
            "run used the deterministic FakeProvider",
            "the numbers are the baseline's, not this run's",
        ),
    )


def _stub_system(_question: str, _document: str) -> str:
    """Answer every case the same way: no values, no model, no claim."""
    return STUB_ANSWER


def stub_competitor_side() -> SideArtifacts:
    """The competitor side, driven through the adapter by a deterministic stub.

    Every case goes through :func:`~tests.evaluation.paperqa_adapter.run_case`
    exactly once — the adapter's single-call rule is not weakened for the
    dry run — and is scored from the recorded artifact and the committed
    key. The stub ignores the question and the document, so the recall it
    earns is a measurement of the wire, not of paper-qa.
    """
    versions = _answer_key_versions()
    artifacts: list[Mapping[str, Any]] = []
    matched = 0
    expected_total = 0
    for fixture in CORPUS_FIXTURES:
        key = load_expected(fixture)
        artifact = run_case(_stub_system, fixture, key)
        score = score_artifact(artifact, key)
        artifacts.append(artifact)
        matched += score.matched
        expected_total += score.expected
    basis = ComparisonBasis(
        label="paper-qa (offline stub)",
        fixture_labels=CORPUS_FIXTURES,
        fixture_versions=versions,
        model="",
        budget="",
        verified_capabilities=(
            "fixture rendering",
            "question construction",
            "artifact capture",
            "mechanical scoring",
        ),
        limitations=(
            "a deterministic stub answered every case; no retrieval, model "
            "or provider was involved, so the recall is a wiring "
            "measurement and not a capability measurement"
        ),
    )
    return SideArtifacts(
        basis=basis,
        metrics={STUB_METRIC: (matched, expected_total)},
        source=(
            "the paper-qa adapter driven by a deterministic stub; no model, "
            "retrieval or provider was involved"
        ),
        stub=True,
        artifacts=tuple(artifacts),
        notes=(
            "the fixture labels and version pins are the committed corpus's; "
            "the stub did not run anything that could produce its own",
            "the answer text is the stub's sentence, untouched by the adapter",
        ),
    )


def _real_run_refusals(
    budget: str,
    our_consent: Path | None,
    competitor_approval: Path | None,
) -> tuple[str, ...]:
    """Everything a real mode is missing, including the structural blocker."""
    reasons: list[str] = []
    if not budget.strip():
        reasons.append(
            "the real mode requires a declared budget ceiling; none was given "
            "(brief §6 keeps the figure with the owner)"
        )
    if our_consent is None or not our_consent.is_file():
        reasons.append(
            "the real mode requires our side's outbound-consent record; no "
            "run is started around the consent bridge"
        )
    if competitor_approval is None or not competitor_approval.is_file():
        reasons.append(
            "the real mode requires the owner's approval for the competitor "
            "run; the final competitor list is the owner's decision (brief §6)"
        )
    reasons.append(
        "even with those three, this driver does not run a real comparison: "
        "our side has no model-declaring frozen run (the frozen baseline "
        'declares model "" and the release\'s non-goal is that no task path '
        "calls a model), and brief §1 says a real competitor cannot be "
        "compared against it. A real run needs a new frozen basis from the "
        "LC-P2-01 model-call path first"
    )
    return tuple(reasons)


def run_comparison(
    mode: str,
    repo_root: Path,
    *,
    budget: str = "",
    our_consent: Path | None = None,
    competitor_approval: Path | None = None,
    baseline_path: Path | None = None,
) -> ComparisonRun:
    """Build both sides, ask the six conditions, and return the run.

    :raises ValueError: when ``mode`` is not one of :data:`MODES`.
    :raises RealRunRefusedError: when ``mode`` is ``real``. The refusal happens
        before a side is built, so no provider is constructed.
    :raises FrozenBaselineMovedError: when the frozen baseline no longer pins
        this tree's answer keys.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if mode == REAL:
        raise RealRunRefusedError(_real_run_refusals(budget, our_consent, competitor_approval))
    our_side = frozen_labcairn_side(repo_root, baseline_path=baseline_path)
    competitor_side = stub_competitor_side()
    outcome = assess(our_side.basis, competitor_side.basis)
    metric_pairs = pairs(our_side.metrics, competitor_side.metrics) if outcome.comparable else ()
    return ComparisonRun(
        mode=mode,
        our_side=our_side,
        competitor_side=competitor_side,
        outcome=outcome,
        metric_pairs=metric_pairs,
        disclosures=_disclosures(),
    )


def _disclosures() -> tuple[str, ...]:
    """What the report says about itself, in sentences a reader can check."""
    return (
        "This is a dry run. Neither side called a provider; the run records 0 provider calls.",
        "Our side's numbers are the frozen Phase 1 baseline's, read from "
        f"{BASELINE_PATH.as_posix()}. They came from the deterministic "
        "FakeProvider, so they measure the repository's own tests, not a "
        "model's behaviour.",
        "The competitor side was answered by a deterministic stub. Its answer "
        "computes nothing, so its recall is a wiring measurement, not a "
        "capability measurement.",
        'Both sides declare model "" and budget "", which is why the six '
        "conditions are met. A real competitor declares a model, so this "
        "pairing does not carry to a real run: brief §1 says the frozen "
        "offline baseline cannot be our side of that comparison.",
        "No metric name is measured on both sides: our side counts exact "
        "cells and the competitor side counts the key's expected statistics "
        "recalled by the stub's text. The report prints no pair, because one "
        "name over two denominators would be one number pretending to be "
        "another.",
        "No aggregate and no verdict is computed or rendered.",
    )


def _display_model(basis: ComparisonBasis) -> str:
    """The model as a report cell, with the empty declaration said out loud."""
    return basis.model if basis.model else "(none declared)"


def _display_budget(basis: ComparisonBasis) -> str:
    """The budget as a report cell, with the empty declaration said out loud."""
    return basis.budget if basis.budget else "(none declared)"


def render_report(run: ComparisonRun) -> str:
    """The comparison report, as Markdown.

    The report renders the six rows :func:`assess` produced; it does not
    re-derive them. Pairs are printed only when the sides share a metric
    name and the comparison is comparable, and no aggregate or verdict is
    rendered anywhere.
    """
    lines: list[str] = []
    lines.append(f"# The competitor comparison — {run.mode}")
    lines.append("")
    lines.append(
        f"**Provider calls:** {run.provider_calls} · "
        f"**Our side:** {run.our_side.basis.label} · "
        f"**Competitor side:** {run.competitor_side.basis.label}"
    )
    lines.append("")

    lines.append("## The sides")
    lines.append("")
    lines.append("| side | source | model | budget | stub |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        f"| ours | {run.our_side.source} | "
        f"{_display_model(run.our_side.basis)} | "
        f"{_display_budget(run.our_side.basis)} | "
        f"{'yes' if run.our_side.stub else 'no'} |"
    )
    lines.append(
        f"| competitor | {run.competitor_side.source} | "
        f"{_display_model(run.competitor_side.basis)} | "
        f"{_display_budget(run.competitor_side.basis)} | "
        f"{'yes' if run.competitor_side.stub else 'no'} |"
    )
    lines.append("")

    lines.append("## The six conditions")
    lines.append("")
    lines.append("| # | condition | met | what it checked |")
    lines.append("|---|---|---|---|")
    for number, check in enumerate(run.outcome.conditions, start=1):
        lines.append(
            f"| {number} | {check.name} | {'yes' if check.met else 'no'} | {check.detail} |"
        )
    lines.append("")
    if run.outcome.comparable:
        lines.append(
            "The six conditions are met, so the two sides are comparable — "
            "as the dry-run pairing the disclosures below describe."
        )
    else:
        lines.append(
            "The comparison is refused. The reasons are the unmet rows above, "
            "repeated here so a reader who skipped the table sees them:"
        )
        lines.append("")
        for reason in run.outcome.reasons:
            lines.append(f"- {reason}")
    lines.append("")

    lines.append("## The metric pairs")
    lines.append("")
    if not run.outcome.comparable:
        lines.append("The comparison is refused, so no pair is printed.")
    elif run.metric_pairs:
        lines.append("| metric | pair |")
        lines.append("|---|---|")
        for name, value in run.metric_pairs:
            lines.append(f"| {name} | {value} |")
    else:
        lines.append(
            "No metric name is measured on both sides, so no pair is printed. "
            "Our side counts exact cells; the competitor side counts the key's "
            "expected statistics recalled by the stub's text. Two denominators "
            "under one name would not be one measurement."
        )
    lines.append("")

    lines.append("## What this run does not show")
    lines.append("")
    lines.append("- no model answered either side; both sides declare an empty model")
    lines.append("- no retrieval, provider call or spend happened on either side")
    lines.append(
        "- the competitor side is a stub, so its recall says nothing about paper-qa's capability"
    )
    lines.append(
        "- the competitor side covers the numeric-extraction task only; "
        "unsupported-claim detection and recovery have no competitor artifact "
        "in this dry run"
    )
    lines.append(
        "- our side's numbers are the frozen baseline's, not a re-measurement "
        "of this tree's behaviour"
    )
    lines.append("")

    lines.append("## Disclosures")
    lines.append("")
    for disclosure in run.disclosures:
        lines.append(f"- {disclosure}")
    lines.append("")

    markdown = "\n".join(lines) + "\n"
    found = ranking_pattern().search(markdown)
    if found is not None:
        raise RankingLanguageError(
            f"the rendered report contains the verdict-carrying word "
            f"{found.group(0)!r}; the comparison renders pairs, never a verdict"
        )
    return markdown


def write_report(run: ComparisonRun, output_dir: Path) -> tuple[Path, Path]:
    """Write the Markdown report and the JSON record, and return both paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "comparison-report.md"
    record_path = output_dir / "comparison-record.json"
    report_path.write_text(render_report(run), encoding="utf-8")
    record_path.write_text(
        json.dumps(run.record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path, record_path
