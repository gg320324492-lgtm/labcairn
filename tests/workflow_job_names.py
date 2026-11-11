"""Reading a workflow's job names the way GitHub does.

**Why this is a shared module.** Two witnesses read the job names of every
workflow file: `tests/test_ci_shard_coverage.py` (branch protection identifies
a check by name, so two legs sharing one name are one check) and
`tests/test_shell_ci.py` (which workflow runs the shell's Node witnesses). The
substitution each needs is the same — a matrix job's `name:` is a template, and
GitHub renders it once per matrix leg. A copy per witness is the drift the
project's own history keeps hitting: the `release-dependency-licences
(matrix.os)` literal survived every earlier check precisely because the one
witness that could have caught it compared name *templates*, not rendered names.

So the rendering lives here once, and both witnesses call it.

**The property this module decides.** A name is *rendered* by substituting each
`${{ matrix.<axis> }}` with the axis value of one matrix leg. A name that names
an axis its matrix does not declare is refused rather than passed through as
text: a name GitHub cannot render is not a name a witness may compare, and a
check that cannot look is a check that has been turned off.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from typing import Any, Final

import yaml

#: A GitHub Actions expression naming one matrix dimension.
MATRIX_EXPRESSION: Final[re.Pattern[str]] = re.compile(
    r"\$\{\{\s*matrix\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}"
)

#: Matrix keys that add or remove legs rather than naming an axis.
MATRIX_NON_AXIS_KEYS: Final[frozenset[str]] = frozenset({"include", "exclude"})


class UnrenderableJobNameError(ValueError):
    """A job name GitHub cannot render, so no witness may compare it."""


def load_workflows(directory: Any) -> list[Any]:
    """Every workflow file in a directory, parsed, sorted by name."""
    paths = sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])
    documents = []
    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            msg = f"{path.name} is not a workflow mapping"
            raise UnrenderableJobNameError(msg)
        documents.append((path, document))
    return documents


def _matrix_axes(job: dict[str, Any], workflow: str, job_key: str) -> dict[str, list[Any]]:
    """The matrix axes a job declares, as axis → list of values."""
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return {}
    axes: dict[str, list[Any]] = {}
    for axis, values in matrix.items():
        if axis in MATRIX_NON_AXIS_KEYS:
            continue
        if not isinstance(values, list):
            msg = (
                f"{workflow}: job {job_key} declares matrix.{axis} as something "
                "other than a list of legs"
            )
            raise UnrenderableJobNameError(msg)
        axes[axis] = values
    return axes


def _matrix_legs(axes: dict[str, list[Any]]) -> Iterator[dict[str, Any]]:
    """The cartesian product of a job's matrix axes."""
    if not axes:
        return
    names = sorted(axes)
    for values in itertools.product(*(axes[axis] for axis in names)):
        yield dict(zip(names, values, strict=True))


def _render_name(name: str, leg: dict[str, Any], workflow: str, job_key: str) -> str:
    """Substitute one matrix leg into a job name."""

    def substitute(match: re.Match[str]) -> str:
        axis = match.group(1)
        if axis not in leg:
            msg = (
                f"{workflow}: job {job_key} names matrix.{axis}, which its matrix does not declare"
            )
            raise UnrenderableJobNameError(msg)
        return str(leg[axis])

    return MATRIX_EXPRESSION.sub(substitute, name)


def rendered_job_names(document: dict[str, Any], workflow: str) -> list[str]:
    """Every name the workflow's jobs report to branch protection.

    A job with no matrix reports its `name:` (or its job key) as written. A job
    with a matrix reports one name per leg, with each `${{ matrix.<axis> }}`
    replaced by that leg's value — which is what makes a literal `(matrix.os)`
    collide with itself across legs, the defect this module exists to catch.
    """
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        msg = f"{workflow} declares no jobs"
        raise UnrenderableJobNameError(msg)
    names: list[str] = []
    for job_key, job in jobs.items():
        if not isinstance(job, dict):
            msg = f"{workflow}: job {job_key} is not a mapping"
            raise UnrenderableJobNameError(msg)
        name = str(job.get("name", job_key))
        axes = _matrix_axes(job, workflow, job_key)
        legs = list(_matrix_legs(axes))
        if not axes:
            names.append(name)
            continue
        names.extend(_render_name(name, leg, workflow, job_key) for leg in legs)
    return names


def duplicate_job_names(documents: list[tuple[Any, dict[str, Any]]]) -> list[str]:
    """Names more than one job or matrix leg would report, across workflows."""
    all_names: list[str] = []
    for path, document in documents:
        all_names.extend(rendered_job_names(document, path.name))
    return sorted({name for name in all_names if all_names.count(name) > 1})
