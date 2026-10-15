"""T09 — the negative control: prove that "unknown folded into 0" is *detectable*.

Everything else in this suite asserts what the code does. This file asserts
what would happen if it stopped doing that — which is the requirement that
*"if any code path treats unknown as 0, the test must fail."*

The instrument
--------------
:func:`usage_folds` is a small AST detector with three rules, aimed at the three
shapes the fold actually takes in practice:

``zero-default``
    ``total or 0`` / ``total or 0.0``. This is not a hypothetical: it is
    OpenHands' ``cost = combined_metrics.accumulated_cost or 0.0``
    (``conversation/visualizer/default.py:447``), which ADR-0002 §A2 names as
    the failure that lets a budget silently never trip.

``zero-return``
    A function annotated to return a usage type whose body returns a bare ``0``
    — the same lie wearing a return type instead of an ``or``.

``coercion``
    ``int(value)`` / ``float(value)`` where ``value`` is annotated as a usage
    type. The number has to come out through :func:`require_known`, which
    raises on an unknown; a direct coercion is a fold with extra steps.

Why an AST check at all, when ``mypy --strict`` already refuses most of these?
Two reasons. First, mypy catches the *type* errors — ``int(unknown)`` is
rejected because ``Unknown`` has no ``__int__`` — but it says nothing about
``x or 0``, which is well-typed for any object that is merely truthy. Second,
a detector can be pointed at a deliberate violation to prove it works; mypy
rejection is demonstrated in the delivery report rather than asserted here,
because running mypy inside the suite would make the suite depend on a type
checker being installed and on its cache state.

The control runs three ways, in increasing order of how little anyone has to
take on faith:

1. three synthetic violations in a string, one rule each;
2. a compliant snippet, to show the detector is not simply reporting something;
3. **:func:`_fold_unknown_to_zero` in this very file**, which is real,
   compiled, runnable code — and the detector is pointed at this file and
   required to find it.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from labcairn.core.providers import (
    Known,
    Unknown,
    UnknownReason,
    UnmeasuredQuantityError,
    UsageValue,
    canonical_json,
    require_known,
)

#: Type names whose values may be unknown. Matched with word boundaries so
#: `UnknownReason` does not match `Unknown`.
_USAGE_TYPE_PATTERN = re.compile(r"\b(Known|Unknown|UsageValue)\b")

_COERCERS = frozenset({"int", "float", "round"})


@dataclass(frozen=True, slots=True)
class Fold:
    """One detected instance of "an unknown measurement became a number"."""

    rule: str
    line: int
    detail: str

    def __str__(self) -> str:
        return f"{self.rule} at line {self.line}: {self.detail}"


# ---------------------------------------------------------------------------
# The detector
# ---------------------------------------------------------------------------


def _is_zero(node: ast.expr) -> bool:
    if not isinstance(node, ast.Constant):
        return False
    return isinstance(node.value, (int, float)) and not node.value


def _describe(node: ast.expr) -> str:
    return ast.unparse(node)


def usage_typed_names(tree: ast.AST) -> set[str]:
    """Annotation-driven rather than inference-driven: conservative, needs no type
    checker, and a variable that *should* be a usage value but lost its
    annotation is reported as a miss rather than silently ignored.
    """
    names: set[str] = set()

    def matches(annotation: ast.expr | None) -> bool:
        return annotation is not None and bool(_USAGE_TYPE_PATTERN.search(ast.unparse(annotation)))

    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and matches(node.annotation):
            names.add(node.arg)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and matches(node.annotation)
        ):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and matches(node.returns):
            names.add(node.name)
    return names


def usage_folds(tree: ast.AST) -> list[Fold]:
    """Every place the module turns a possibly-unknown quantity into a number."""
    folds: list[Fold] = []
    usage_names = usage_typed_names(tree)

    for node in ast.walk(tree):
        # Rule 1 — `value or 0` / `value or 0.0`.
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            zeros = [value for value in node.values if _is_zero(value)]
            others = [value for value in node.values if not _is_zero(value)]
            if zeros and others:
                folds.append(
                    Fold(
                        rule="zero-default",
                        line=node.lineno,
                        detail=f"`{_describe(others[0])} or {len(zeros) * '0'}` substitutes a zero "
                        f"for a possibly-unmeasured value",
                    )
                )

        # Rule 3 — `int(value)` on a usage-typed name.
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _COERCERS
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in usage_names
        ):
            folds.append(
                Fold(
                    rule="coercion",
                    line=node.lineno,
                    detail=f"`{node.func.id}({node.args[0].id})` bypasses require_known()",
                )
            )

    # Rule 2 — a usage-typed function that returns a bare zero.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _USAGE_TYPE_PATTERN.search(ast.unparse(node.returns) if node.returns else ""):
            continue
        zero_names: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Return) and inner.value is not None:
                if _is_zero(inner.value):
                    folds.append(
                        Fold(
                            "zero-return",
                            inner.lineno,
                            "returns a bare 0 from a usage-typed function",
                        )
                    )
                elif isinstance(inner.value, ast.Name) and inner.value.id in zero_names:
                    folds.append(
                        Fold(
                            "zero-return",
                            inner.lineno,
                            f"returns `{inner.value.id}`, a local assigned a bare zero",
                        )
                    )
            elif isinstance(inner, ast.Assign) and _is_zero(inner.value):
                zero_names.update(
                    target.id for target in inner.targets if isinstance(target, ast.Name)
                )
    return folds


def folds_in_source(source: str, *, filename: str = "<string>") -> list[Fold]:
    return usage_folds(ast.parse(source, filename=filename))


def folds_in_tree(repo_root: Path, subdirectory: str) -> list[str]:
    """Every fold found under ``subdirectory``, as readable one-per-line strings."""
    findings: list[str] = []
    root = repo_root / subdirectory
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fold in usage_folds(tree):
            findings.append(f"{path.relative_to(repo_root).as_posix()}: {fold}")
    return findings


# ---------------------------------------------------------------------------
# A deliberately wrong implementation, defined here on purpose
# ---------------------------------------------------------------------------


def _provider_omitted_as_zero() -> UsageValue:
    """WRONG ON PURPOSE. The OpenHands failure, faithfully reduced.

    ADR-0002 §A2 quotes it as
    ``MetricsSnapshot.accumulated_cost: float = Field(default=0.0, ge=0.0)``
    (``metrics.py:83-84``) — the *default value* is the lie, not the ``or``.
    A record whose "not measured" and "measured zero" share a representation
    cannot tell them apart later, no matter what the caller does.

    Written here, in a real file, so the detector can be pointed at real code
    rather than at a string of source embedded in a test. Never call this from
    anywhere else — the tests below exist to show it is caught and that the
    honest path refuses the same situation.
    """
    # mypy rejects this too (``int`` is not ``UsageValue``), which is the type
    # system doing its half of the work. The ignore is needed to write the bug.
    return 0  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Control 1 — synthetic violations, one rule each
# ---------------------------------------------------------------------------

_ZER0_DEFAULT_SOURCE = """
from labcairn.core.providers.usage import UsageValue

def render_cost(total: UsageValue) -> float:
    return total or 0.0
"""

_ZERO_RETURN_SOURCE = """
from labcairn.core.providers.usage import UsageValue

def unmeasured() -> UsageValue:
    return 0
"""

_COERCION_SOURCE = """
from labcairn.core.providers.usage import UsageValue

def tokens(value: UsageValue) -> int:
    return int(value)
"""


def test_detector_flags_a_zero_default() -> None:
    """Rule 1: the OpenHands shape."""
    folds = folds_in_source(_ZER0_DEFAULT_SOURCE)
    assert [fold.rule for fold in folds] == ["zero-default"]
    assert "or 0" in folds[0].detail


def test_detector_flags_a_zero_return() -> None:
    """Rule 2: the same lie behind a return annotation."""
    folds = folds_in_source(_ZERO_RETURN_SOURCE)
    assert [fold.rule for fold in folds] == ["zero-return"]


def test_detector_flags_a_coercion() -> None:
    """Rule 3: a number that skipped ``require_known``."""
    folds = folds_in_source(_COERCION_SOURCE)
    assert [fold.rule for fold in folds] == ["coercion"]
    assert "require_known" in folds[0].detail


def test_detector_is_quiet_on_compliant_code() -> None:
    """A detector that flags everything detects nothing. This is the other half."""
    compliant = """
from labcairn.core.providers.usage import Known, UsageValue, merge, require_known

def tokens(value: UsageValue) -> int:
    return require_known(value)

def running_total(values: list[UsageValue]) -> UsageValue:
    running: UsageValue = Known(0)
    for value in values:
        running = merge(running, value)
    return running
"""
    assert folds_in_source(compliant) == []


# ---------------------------------------------------------------------------
# Control 2 — the real file, real code
# ---------------------------------------------------------------------------


def test_detector_finds_the_wrong_helper_written_above() -> None:
    """Point the detector at this file and require it to find :func:`_provider_omitted_as_zero`.

    This is the negative control proper. It is not a string of planted source
    parsed in isolation — it is the module the test runner is executing right
    now, with the same syntax the project ships.

    Two findings are expected, and both are correct:

    * the ``return 0`` in :func:`_provider_omitted_as_zero` — the planted
      ``Field(default=0.0)``;
    * the ``unmeasured or 0`` inside
      :func:`test_the_or_zero_idiom_cannot_fold_an_unknown`, which is written
      there deliberately to demonstrate the idiom. Rule 1 is syntactic, so it
      fires on that line too — which is the behaviour its own docstring claims.
    """
    folds = folds_in_source(Path(__file__).read_text(encoding="utf-8"), filename=__file__)

    # Sorted by line: the detector walks the AST breadth-first and runs its
    # rules in separate passes, so it promises the findings, not their order.
    ordered = sorted(folds, key=lambda fold: fold.line)
    assert [fold.rule for fold in ordered] == ["zero-return", "zero-default"], [
        str(fold) for fold in ordered
    ]


def test_the_wrong_helper_really_does_return_zero() -> None:
    """The planted bug behaves like the bug it models.

    Without this, the control above could pass on a detector that flags the
    right *line* for the wrong reason — or on a flagged line that is harmless.
    This confirms the flagged code really does destroy the distinction.
    """
    # Typed `object` deliberately: the helper is annotated `-> UsageValue`, so
    # mypy already knows it cannot return 0 and would reject the comparison.
    # The bug lives at runtime, where the annotation is a claim, not a fact.
    lied: object = _provider_omitted_as_zero()

    assert lied == 0

    # In Python the bare 0 is at least a *different object* from a measured
    # zero — dataclass equality is class-sensitive. That is where the damage is
    # really done though: at the serialisation boundary, which is where a usage
    # figure gets recorded and later read. On the wire the two are identical.
    assert Known(0) != 0  # type: ignore[comparison-overlap]
    assert canonical_json({"input_tokens": lied}) == canonical_json(
        {"input_tokens": Known(0).value}
    )

    # The honest encoding is tagged, so it can never collide with a bare number.
    honest = Unknown(UnknownReason.PROVIDER_OMITTED)
    measured = canonical_json({"input_tokens": Known(0).to_wire()})
    unmeasured = canonical_json({"input_tokens": honest.to_wire()})

    assert measured == '{"input_tokens":{"known":0}}'
    assert unmeasured == '{"input_tokens":{"unknown":"provider_omitted"}}'
    assert unmeasured != canonical_json({"input_tokens": lied})

    with pytest.raises(UnmeasuredQuantityError):
        require_known(honest)


def test_the_or_zero_idiom_cannot_fold_an_unknown() -> None:
    """``x or 0`` is banned by rule 1, and for a second, independent reason.

    ``Unknown`` is truthy, so ``value or 0`` hands back the ``Unknown`` rather
    than a zero — the idiom happens not to destroy the measurement here. It is
    still banned, because that is a property of this type's truthiness rather
    than of the type system: add a ``__bool__`` to ``Unknown`` (a plausible
    "make unknown falsy" convenience) and the very same line silently becomes
    the bug. Rule 1 keeps the code from ever being in that position.

    This is also why rule 1 is syntactic: it fires on the *shape*, not on
    whether the fold happens to succeed today.
    """
    unmeasured = Unknown(UnknownReason.PROVIDER_OMITTED)
    coerced: object = unmeasured or 0

    # The `or` hands back the Unknown itself, untouched.
    assert coerced == unmeasured


# ---------------------------------------------------------------------------
# Control 3 — the shipped source is clean
# ---------------------------------------------------------------------------


def test_shipped_source_contains_no_usage_fold(repo_root: Path) -> None:
    """The guard applied to ``src/labcairn/**``: this is the actual gate.

    Scope is the whole package rather than only ``providers/`` so that LC-P1-03's
    adapters, budget checks and any provider that follows inherit the check
    without anyone having to remember to extend it.
    """
    findings = folds_in_tree(repo_root, "src/labcairn")

    assert not findings, (
        "an unknown measurement is being turned into a number in src/labcairn:\n"
        + "\n".join(findings)
    )


def test_the_gate_actually_covers_the_provider_package(repo_root: Path) -> None:
    """Guard against the guard: confirm the sweep reaches files that exist.

    A sweep over a mistyped path finds nothing and passes. This asserts the same
    sweep finds the provider modules, so a green gate means "checked", not
    "nothing to check".
    """
    providers = repo_root / "src" / "labcairn" / "core" / "providers"
    sources = sorted(providers.rglob("*.py"))
    names = {path.name for path in sources}

    assert {"usage.py", "protocol.py", "fake.py", "transcripts.py", "__init__.py"} <= names

    # A known-clean module really is clean under the same detector…
    usage_tree = ast.parse((providers / "usage.py").read_text(encoding="utf-8"))
    assert usage_folds(usage_tree) == []
    # …and the detector does fire when pointed at a file that contains one.
    assert usage_folds(ast.parse(Path(__file__).read_text(encoding="utf-8")))
