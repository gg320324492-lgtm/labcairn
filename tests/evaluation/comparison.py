"""Whether a baseline may be compared against this run at all.

**The rule being enforced.** The protocol says it plainly:

    Do not claim superiority over PaperQA2/PaperSpine/others without
    like-for-like matched-task baselines, verified capabilities, and
    documented confidence intervals or limitations.

Three requirements, and a comparison that meets fewer than all three is
**not a comparison**. It is two numbers side by side, and the protocol
names that as something this repository does not ship.

**Why the requirement is a refusal and not a warning.** A comparison that
prints anyway, with a caveat underneath, is a comparison a reader skims.
The protocol's requirement is that the comparison be *like-for-like*, and
the only way to make that true is to refuse the ones that are not. So
:func:`assess` returns a :class:`ComparisonOutcome` whose
``comparable`` is ``False`` whenever a requirement is missing, and the
report then prints the reasons instead of the numbers.

**No ranking, ever.** The protocol forbids claiming superiority, and the
structure of the output is what stops it: the comparison prints **pairs**,
one metric at a time, and it has no way to say which of the two is better.
There is no aggregate verdict to render, because no aggregate verdict is
computed. ``tests/test_evaluation_harness.py`` watches that the rendered
section carries no winner's language.

**What the offline run can be compared against.** Almost nothing, and the
harness says so: the offline run used the deterministic ``FakeProvider``,
which is not *"a declared model, version and parameter set"*, and the
repository's rules are that *"mock-only success is insufficient"*. So a
baseline document that does not declare a model cannot be matched against
this run, and the report says which requirement failed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from .model import ComparisonOutcome

#: The requirements the protocol names, and the word each one is checked by.
REQUIREMENTS: Final[tuple[tuple[str, str], ...]] = (
    ("matched_task", "the baseline and the run must cover the same tasks"),
    ("verified_capabilities", "the baseline must declare the capabilities it verified"),
    (
        "documented_limits",
        "the baseline must document confidence intervals or limitations",
    ),
)


@dataclass(frozen=True, slots=True)
class ComparisonBasis:
    """What one side of a comparison says about itself.

    The same shape is used for the run and for the baseline, so the two are
    compared the same way — and so a baseline document that leaves a field
    out is visibly incomplete rather than quietly defaulted.
    """

    #: What this side is.
    label: str
    #: The tasks covered, by name.
    fixture_labels: tuple[str, ...] = ()
    #: The version of each task, so that two runs of "the same" fixture can
    #: be told apart.
    fixture_versions: Mapping[str, str] = field(default_factory=dict)
    #: The declared model: name, version and parameters, as one string.
    model: str = ""
    #: The declared budget.
    budget: str = ""
    #: The capabilities that were verified.
    verified_capabilities: tuple[str, ...] = ()
    #: The documented limitations.
    limitations: str = ""
    #: The documented confidence intervals.
    confidence_intervals: str = ""

    @classmethod
    def from_document(cls, document: Mapping[str, Any], label: str) -> ComparisonBasis:
        """Read a basis out of a JSON document."""
        fixtures = document.get("fixtures")
        names: tuple[str, ...] = ()
        versions: dict[str, str] = {}
        if isinstance(fixtures, Mapping):
            raw_names = fixtures.get("names")
            if isinstance(raw_names, list):
                names = tuple(str(name) for name in raw_names)
            raw_versions = fixtures.get("versions")
            if isinstance(raw_versions, Mapping):
                versions = {str(key): str(value) for key, value in raw_versions.items()}
        model = document.get("model")
        model_text = ""
        if isinstance(model, Mapping):
            model_text = ", ".join(
                f"{key}={model[key]}" for key in sorted(model) if model[key] is not None
            )
        elif model is not None:
            model_text = str(model)
        budget = document.get("budget")
        capabilities = document.get("verified_capabilities")
        intervals = document.get("confidence_intervals")
        return cls(
            label=label,
            fixture_labels=names,
            fixture_versions=versions,
            model=model_text,
            budget="" if budget is None else str(budget),
            verified_capabilities=(
                tuple(str(item) for item in capabilities) if isinstance(capabilities, list) else ()
            ),
            limitations=str(document.get("limitations", "")),
            confidence_intervals="" if intervals is None else str(intervals),
        )


@dataclass(frozen=True, slots=True)
class BaselineDocument:
    """A baseline document: what it says about itself, and its numbers."""

    #: The basis, checked against the run's.
    basis: ComparisonBasis
    #: The metric numbers, as numerator over denominator.
    metrics: Mapping[str, tuple[int, int]] = field(default_factory=dict)


def assess(run: ComparisonBasis, baseline: ComparisonBasis) -> ComparisonOutcome:
    """Decide whether the two may be compared, and say why not when they may not."""
    reasons: list[str] = []

    if run.fixture_labels != baseline.fixture_labels:
        reasons.append(
            "the tasks are not matched: the run covers "
            f"{list(run.fixture_labels)} and the baseline covers "
            f"{list(baseline.fixture_labels)}"
        )
    if run.fixture_versions != baseline.fixture_versions:
        reasons.append(
            "the task versions are not matched: the run's versions are "
            f"{dict(run.fixture_versions)} and the baseline's are "
            f"{dict(baseline.fixture_versions)}"
        )
    if run.model != baseline.model:
        reasons.append(
            "the models are not matched: the run declares "
            f"{run.model!r} and the baseline declares {baseline.model!r}"
        )
    if run.budget != baseline.budget:
        reasons.append(
            f"the budgets are not matched: the run declares {run.budget!r} and "
            f"the baseline declares {baseline.budget!r}"
        )
    if not baseline.verified_capabilities:
        reasons.append(
            "the baseline declares no verified capabilities, so the two sides "
            "are not known to be capable of the same thing"
        )
    if not baseline.limitations and not baseline.confidence_intervals:
        reasons.append(
            "the baseline documents neither confidence intervals nor "
            "limitations, so its numbers cannot be read with any stated "
            "uncertainty"
        )

    if reasons:
        return ComparisonOutcome(comparable=False, reasons=tuple(reasons))
    return ComparisonOutcome(comparable=True, reasons=())


def load_baseline(path: Path) -> BaselineDocument:
    """Read a baseline document from a JSON file.

    The document carries two things: the **basis** — what the baseline says
    about itself, which is what :func:`assess` checks against this run —
    and the **numbers**, which are only ever printed if the basis matched.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        msg = f"the baseline at {path} is not a JSON object"
        raise ValueError(msg)
    label = str(document.get("label", path.stem))
    raw_metrics = document.get("metrics")
    metrics: dict[str, tuple[int, int]] = {}
    if isinstance(raw_metrics, Mapping):
        for key, value in raw_metrics.items():
            if not isinstance(value, Mapping):
                continue
            numerator = value.get("numerator")
            denominator = value.get("denominator")
            if isinstance(numerator, int) and isinstance(denominator, int):
                metrics[str(key)] = (numerator, denominator)
    return BaselineDocument(
        basis=ComparisonBasis.from_document(document, label),
        metrics=metrics,
    )


def pairs(
    run_values: Mapping[str, tuple[int, int]],
    baseline_values: Mapping[str, tuple[int, int]],
) -> tuple[tuple[str, str], ...]:
    """The per-metric pairs a comparable comparison prints.

    A pair, never a verdict: ``"metric name: 66/66 against 60/66"``. There
    is deliberately no aggregate, so there is nothing for the report to
    render as a winner.
    """
    lines: list[tuple[str, str]] = []
    for key in sorted(set(run_values) & set(baseline_values)):
        run_numerator, run_denominator = run_values[key]
        base_numerator, base_denominator = baseline_values[key]
        lines.append(
            (
                key,
                f"{run_numerator}/{run_denominator} against {base_numerator}/{base_denominator}",
            )
        )
    return tuple(lines)
