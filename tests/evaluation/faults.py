"""The crash matrix's fault-injection coverage, read out of the matrix.

**Why this module exists.** The recovery metric's denominator was the number
of test cases the crash matrix collected, and the report called that number
*"the fault-injection scenarios the matrix ran"* — *"one collected test case
is one injected fault"*. Neither half of that is true. The matrix collects
more cases than it injects faults (two of its cases re-run a fault an
earlier case injected), it injects more faults than it has cases (one case
kills three child processes, one after another), and it injects **four**
faults, not eight. So the number the report called "the number of faults"
was the number of test functions, and a reader checking it against the
matrix would find something else.

**What the number should be.** The matrix's coverage is complete at the
layer: every member of the product's :class:`CrashPoint` enumeration is
injected by some case in the file. **That** is the fact the metric should
carry — one crash point, counted once, however many cases inject it — and
this module reads it out of the matrix rather than out of a number somebody
wrote down.

**How it is read.** The matrix's cases name the crash point they inject in
their own source, so the coverage is read by parsing that source: every
``CrashPoint.<member>`` a case mentions is a fault that case injects. The
enumeration's own members come from the product, so a crash point the
product adds and the matrix does not cover is **visible** — the denominator
grows and the rate falls, rather than the metric quietly measuring a
smaller set than it used to.

**Why it is parsed rather than imported.** A case's fault is an argument to
``arm()`` inside the case's body, so there is nothing to import: the only
place the fact is written down is the source. Parsing it is reading the
matrix's own statement of what it does.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The file whose cases are the fault-injection scenarios.
CRASH_MATRIX_FILE: Final = "test_recovery_crash_matrix.py"

#: The name the matrix gives the product's enumeration.
_CRASH_POINT: Final = "CrashPoint"

#: The prefix a case's name carries.
_CASE_PREFIX: Final = "test_"


@dataclass(frozen=True, slots=True)
class CrashMatrixCoverage:
    """Which crash points the crash matrix injects, and which cases inject them.

    **The counts name what they count.** ``defined`` is the number of crash
    points the product has; ``covered`` is the number the matrix injects;
    ``missing`` names the ones it does not.
    """

    #: The crash points the product defines, by member name.
    defined: tuple[str, ...]
    #: The crash points the matrix injects, by member name.
    covered: tuple[str, ...]
    #: The crash points the matrix never injects, by member name.
    missing: tuple[str, ...]
    #: Which case injects which crash point, by case name.
    by_case: Mapping[str, tuple[str, ...]]

    def cases_for(self, member: str) -> tuple[str, ...]:
        """The cases that inject this crash point."""
        return tuple(name for name, points in self.by_case.items() if member in points)


def _members_mentioned(node: ast.AST, members: frozenset[str]) -> tuple[str, ...]:
    """The crash-point members a piece of source names."""
    found: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Attribute):
            continue
        if child.attr not in members:
            continue
        if not isinstance(child.value, ast.Name):
            continue
        if child.value.id != _CRASH_POINT:
            continue
        if child.attr not in found:
            found.append(child.attr)
    return tuple(found)


def read_crash_matrix(repo_root: Path) -> CrashMatrixCoverage:
    """Read the crash matrix's coverage out of the matrix itself.

    Raises when the matrix is not in the tree, rather than reporting a
    coverage of nothing: a matrix that is not there is a missing file, and a
    missing file reported as "no crash points are covered" would be a
    measurement of a tree that does not exist.
    """
    from labcairn.recovery.contracts import CrashPoint

    path = repo_root / "tests" / CRASH_MATRIX_FILE
    if not path.is_file():
        msg = f"the crash matrix is not in the tree: {path} does not exist"
        raise FileNotFoundError(msg)

    members = frozenset(CrashPoint.__members__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    by_case: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith(_CASE_PREFIX):
            continue
        points = _members_mentioned(node, members)
        if points:
            by_case[node.name] = points

    covered = tuple(sorted({member for points in by_case.values() for member in points}))
    defined = tuple(sorted(members))
    missing = tuple(member for member in defined if member not in covered)
    return CrashMatrixCoverage(
        defined=defined,
        covered=covered,
        missing=missing,
        by_case=by_case,
    )
