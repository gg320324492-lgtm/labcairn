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

**The property this module decides.** A name is *rendered* the way GitHub
renders it, because the witness compares the name branch protection sees. Three
shapes, three answers, and each one is witnessed in `tests/test_shell_ci.py`:

* **A job with a matrix, naming one of its axes** — substituted once per leg.
  This is the shape every templated name in the tree has.
* **A job with a matrix, naming an axis that matrix does not declare** —
  refused. GitHub would collapse the expression to nothing, which is how two
  unrelated jobs end up sharing a check name; a name whose axis is not the
  matrix's own is a mistake in the workflow, and a check that cannot look is a
  check that has been turned off.
* **A job with no matrix at all** — rendered as GitHub renders it: an
  undefined `${{ matrix.<axis> }}` expands to the **empty string**, so
  `one (${{ matrix.os }})` and `two (${{ matrix.os }})` both become `one ()`
  and `two ()`, and `one (${{ matrix.os }})` twice becomes one name reported by
  two jobs. Passing the literal through instead — the shape this module had
  before 2026-11-11 — makes the witness see two distinct strings while GitHub
  sees what it sees, and a hole in the thing that watches job names is the hole
  the `release-dependency-licences (matrix.os)` collision lived in.

**What this module does not model: `include` and `exclude`.** A matrix that
adds or removes legs through those keys is refused rather than half-expanded.
GitHub's rules for them (an `include` leg merges into the combinations it
matches, and adds one when it names a value no axis holds) are not implemented
here, and an expansion that gets them wrong reports a *set of legs* that is not
the set CI runs — which is worse than refusing, because a wrong set is the
green a collision needs. Today no workflow in `.github/workflows/` declares
either key; `tests/test_shell_ci.py` watches that, so a refusal is always a new
shape arriving and never background noise. Adding one means extending this
module to GitHub's rules and moving that witness with it.
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
    """The matrix axes a job declares, as axis → list of values.

    **`include` and `exclude` are refused, not skipped.** Before 2026-11-11 they
    were silently dropped, so a matrix that added a leg with `include` reported
    the legs of the axes alone — a *smaller* set than CI runs, and a name
    collision introduced by the missing leg stayed invisible. Skipping is the
    failure mode a watching mechanism must not have: the witness stays green
    because it never saw the leg. Refusing says the same thing out loud.
    """
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return {}
    axes: dict[str, list[Any]] = {}
    for axis, values in matrix.items():
        if axis in MATRIX_NON_AXIS_KEYS:
            msg = (
                f"{workflow}: job {job_key} declares matrix.{axis}, and this module "
                "does not model it — see its docstring. The legs `include` and "
                "`exclude` produce are not the cartesian product of the axes, so "
                "skipping them would report a job-name set CI never runs."
            )
            raise UnrenderableJobNameError(msg)
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


def _render_without_matrix(name: str) -> str:
    """A name a job with no matrix reports, rendered as GitHub renders it.

    An undefined `${{ matrix.<axis> }}` expands to the **empty string**. The
    name text is otherwise kept, so `one (${{ matrix.os }})` becomes `one ()`.
    The parentheses survive; only the expression vanishes.
    """
    return MATRIX_EXPRESSION.sub("", name)


def rendered_job_names(document: dict[str, Any], workflow: str) -> list[str]:
    """Every name the workflow's jobs report to branch protection.

    A job with a matrix reports one name per leg, with each
    `${{ matrix.<axis> }}` replaced by that leg's value — which is what makes a
    literal `(matrix.os)` collide with itself across legs, the defect this
    module exists to catch. A job with no matrix reports its `name:` (or its
    job key) with every matrix expression expanded to nothing, the way GitHub
    expands it; see the docstring for why the literal is not passed through.
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
        if not axes:
            names.append(_render_without_matrix(name))
            continue
        names.extend(_render_name(name, leg, workflow, job_key) for leg in _matrix_legs(axes))
    return names


def duplicate_job_names(documents: list[tuple[Any, dict[str, Any]]]) -> list[str]:
    """Names more than one job or matrix leg would report, across workflows."""
    all_names: list[str] = []
    for path, document in documents:
        all_names.extend(rendered_job_names(document, path.name))
    return sorted({name for name in all_names if all_names.count(name) > 1})
