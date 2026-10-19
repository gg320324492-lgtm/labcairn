"""The renderer: the figure it draws, and the determinism it claims.

LC-P1-10 T07 is the subtask that produces a **figure**, and this file is
where the figure's claims are checked. There are four kinds of claim here,
and each is checked against the thing that could break it.

**The figure's numbers are the operator's numbers.** The renderer is given
the operator's result object and plots it; it does not re-read the file and
it does not re-implement the aggregate. So the tests here build the result
by *running the grouped operator over the corpus* and hand that object to
the renderer, and then check that what came out is the operator's table and
not a second reading of the same file.

**``None`` is not a refusal.** The run path's protocol says ``render()``
returns the figure's bytes, or ``None`` when the result is not a figure. Two
things are not a figure -- a result that is not a table, and a result from
an operator the recipe does not name -- and everything else is a refusal
that names what is wrong.

**Untrusted text is data.** A group name is imported text and ends up in the
SVG. A group named ``<script>alert(1)</script>`` must render escaped, and
the SVG must contain no ``<script`` element: an SVG embedded in an HTML
report is a script context, and the escaping is only safe if it holds at
the source.

**Determinism is demonstrated, not asserted.** Two renders in one process
must have the same bytes; two renders in two processes must have the same
bytes; and the controls that make those true are the ones ADR-0012
measured -- the **date** governs renders within a process and the **salt**
governs renders across processes, and **PNG needs neither**. A control that
cannot be shown to matter does not belong, so the mutation table in the
delivery report names, for each control, the test that fails when it is
removed.

The helpers here are **local to this file**: the corpus helpers come from
the project's own ``tests/analysis_fixtures.py``, but the recipe builder,
the renderer builder and the out-of-process render program are this file's
own, because they are this file's business and a shared helper would be a
second place for them to drift.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import pytest
from analysis_fixtures import corpus_selection, corpus_source

from labcairn.analysis.chart import render as render_module
from labcairn.analysis.chart.recipe import (
    ChartRecipe,
    DataRecipe,
    Encoding,
    FigureFormat,
    Mark,
    Output,
    SelectionSpec,
)
from labcairn.analysis.chart.render import (
    CHART_OPERATOR_ID,
    FIGURE_SIZE,
    HISTOGRAM_BINS,
    INTERPRETATION_MARKER,
    MPL_CONFIG_DIR,
    RC_PARAMS_SHA256,
    RC_PARAMS_SOURCE,
    SVG_HASHSALT,
    ChartArgs,
    FigureRefusedError,
    FigureResult,
    FigureValue,
    MatplotlibFigureRenderer,
)
from labcairn.analysis.manifest import current_environment, read_recipe
from labcairn.analysis.operators import Operator, OperatorArgs, RegisteredOperator
from labcairn.analysis.operators.grouped import (
    AGGREGATE,
    GroupAggregate,
    GroupedArgs,
    GroupedResult,
)
from labcairn.analysis.selection import MissingPolicy, RowRange, RowSet, Selection


#: The contract the run path (LC-P1-10 T09) is given.
#:
#: A **local** copy, because the run path must not import this module and
#: this module must not import the run path: two spellings of one protocol
#: is the failure this project keeps paying for, and the run path owns the
#: protocol. What this copy is for is the *shape* -- so that the renderer
#: is checked against the shape the run path will use, and not against
#: whatever the renderer happens to offer.
@runtime_checkable
class FigureRenderer(Protocol):
    """The renderer the run path is given."""

    def prepare(self) -> None:
        """Put the render environment into its declared state."""
        ...

    def render(self, operator_id: str, result: Any) -> bytes | None:
        """The figure's bytes, or None when this result is not a figure."""
        ...


#: The program that renders in **another interpreter**.
#:
#: It has to be a separate process, because the salt's effect cannot be
#: seen from inside one: matplotlib generates a fresh random salt per
#: interpreter, and within a single process the salt is constant. A test
#: that rendered twice in one process would pass with the salt removed, and
#: that is a test that looks like a test and is not one.
_OUT_OF_PROCESS = """
import hashlib, json, sys
from pathlib import Path

from labcairn.analysis.chart.recipe import ChartRecipe
from labcairn.analysis.chart.render import MatplotlibFigureRenderer
from labcairn.analysis.operators.grouped import GroupedResult
from labcairn.analysis.manifest import read_recipe

payload = json.loads(sys.stdin.read())
recipe = ChartRecipe.model_validate(payload["recipe"])
result = GroupedResult.model_validate(payload["result"])
root = Path(payload["root"])
reference = read_recipe(root, payload["recipe_path"])
renderer = MatplotlibFigureRenderer(recipe=recipe, recipe_ref=reference, workspace_root=root)
renderer.prepare()
if payload.get("unset_salt"):
    import matplotlib
    matplotlib.rcParams["svg.hashsalt"] = None
data = renderer.render(payload["operator_id"], result)
sys.stdout.write(hashlib.sha256(data).hexdigest())
"""


@dataclass(frozen=True, slots=True)
class _Drawn:
    """A figure and the recipe and result it was drawn from."""

    recipe: ChartRecipe
    result: GroupedResult
    renderer: MatplotlibFigureRenderer
    root: Path


def _recipe(
    *,
    mark: Mark = Mark.BAR,
    figure_format: FigureFormat = FigureFormat.SVG,
    columns: tuple[str, ...] = ("group", "value"),
    x: str = "group",
    y: str = "value",
    title: str = "Mean by group",
    x_label: str = "group",
    y_label: str = "mean",
    caption: str = "The mean of each group.",
    interpretation: str | None = None,
    dpi: int = 200,
    source: str = "runs/exp1.csv",
    by: str = "group",
    of: str = "value",
    operator: str = "labcairn.analysis.grouped_aggregate@1.0.0",
    parameters: dict[str, Any] | None = None,
) -> ChartRecipe:
    """A recipe, as a person would write it down."""
    spec = SelectionSpec(
        source=source,
        columns=columns,
        rows=RowRange(2, 17),
        missing=MissingPolicy.EXCLUDE,
    )
    if parameters is None:
        parameters = {
            "aggregate": "labcairn.analysis.mean@1.0.0",
            "by": by,
            "of": of,
        }
    data = DataRecipe(
        operator=operator,
        parameters=parameters,
        selection=spec,
    )
    encoding = Encoding(
        mark=mark,
        x=x,
        y=y,
        title=title,
        x_label=x_label,
        y_label=y_label,
        caption=caption,
        interpretation=interpretation,
    )
    return ChartRecipe(
        data=data,
        encoding=encoding,
        output=Output(format=figure_format, dpi=dpi),
    )


def _selection(columns: tuple[str, ...], rows: RowRange | RowSet) -> Selection:
    """A selection bound to the corpus, for a set of rows the corpus helper
    cannot express."""
    return Selection(
        source_id="corpus",
        content_sha256="a" * 64,
        columns=columns,
        rows=rows,
        missing=MissingPolicy.EXCLUDE,
    )


def _group(
    key: str,
    value: float | None,
    *,
    unit: str | None = None,
    reason: str | None = None,
) -> GroupAggregate:
    """One row of a table the corpus does not have."""
    return GroupAggregate(
        key=key,
        rows=(2,),
        n_used=1 if value is not None else 0,
        n_empty=0 if value is not None else 1,
        n_absent=0,
        n_invalid=0,
        value=value,
        undefined_reason=reason,
        unit=unit,
    )


def _result(
    groups: tuple[GroupAggregate, ...], *, by: str = "group", of: str = "value"
) -> GroupedResult:
    """A table written out by hand, for a shape the corpus does not have.

    The corpus's columns are ``group`` and ``value``, and some of the
    checks below are about a column whose *name* declares a unit -- which
    needs a column called something like ``value (kg)``. The operator's
    own result model is the thing being described here, so it is written
    out rather than computed.
    """
    used = sum(group.n_used for group in groups)
    without = sum(group.n_empty + group.n_absent + group.n_invalid for group in groups)
    return GroupedResult(
        operator_id="labcairn.analysis.grouped_aggregate",
        operator_version="1.0.0",
        aggregate="labcairn.analysis.mean@1.0.0",
        by=by,
        of=of,
        groups=groups,
        n_rows_selected=used + without,
        n_rows_filtered=0,
        n_rows_excluded=without,
        n_rows_ungrouped=0,
        selection=_selection((by, of), RowRange(2, 3)),
    )


def _grouped(
    fixture: str = "groups.csv",
    *,
    rows: str | list[int] = "2-17",
    columns: tuple[str, ...] = ("group", "value"),
    by: str = "group",
    of: str = "value",
) -> GroupedResult:
    """A grouped result, computed by the **operator** over the corpus.

    The operator runs rather than the table being written out by hand,
    because the whole point of the claim under test is that the figure's
    numbers are the operator's numbers: a hand-written table would be a
    second source of truth and the comparison would prove nothing.
    """
    source = corpus_source(fixture)
    if isinstance(rows, str):
        selection = corpus_selection(fixture, {"rows": rows, "columns": list(columns)})
    else:
        selection = _selection(columns, RowSet(tuple(rows)))
    args = GroupedArgs(
        selection=selection,
        aggregate="labcairn.analysis.mean@1.0.0",
        by=by,
        of=of,
    )
    result = AGGREGATE.run(args, source)
    assert isinstance(result, GroupedResult)
    return result


def _drawn(
    tmp_path: Path,
    recipe: ChartRecipe,
    result: GroupedResult,
) -> _Drawn:
    """A renderer over a recipe written to a file, the way the run path has it."""
    root = tmp_path / "workspace"
    (root / "recipes").mkdir(parents=True, exist_ok=True)
    (root / "recipes" / "figure.json").write_bytes(recipe.canonical_bytes())
    reference = read_recipe(root, "recipes/figure.json")
    renderer = MatplotlibFigureRenderer(
        recipe=recipe,
        recipe_ref=reference,
        workspace_root=root,
    )
    return _Drawn(recipe=recipe, result=result, renderer=renderer, root=root)


def _svg(tmp_path: Path, recipe: ChartRecipe, result: GroupedResult) -> str:
    """One rendered SVG, as text."""
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    data = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert data is not None
    return data.decode("utf-8")


def _artists(figure: FigureResult) -> Any:
    """The artists the renderer drew, on a canvas of the test's own.

    The marks' *semantics* -- that a bar's height is the statistic, that a
    line is broken where a group has none, that a histogram's counts are
    the counts the renderer derived -- are not observable in the SVG's
    bytes without re-implementing matplotlib's coordinate transform. So
    this reaches into the module's drawing function, and the tests that
    use it assert the property that matters rather than the shape of the
    drawing.
    """
    import matplotlib.pyplot as plt

    canvas = plt.figure()
    axes = canvas.add_subplot(111)
    render_module._draw_the_mark(axes, figure)
    return axes


def _described(recipe: ChartRecipe, result: GroupedResult) -> FigureResult:
    """The figure the chart operator describes, without drawing it."""
    from labcairn.analysis import catalog

    registered = catalog.operator_for(CHART_OPERATOR_ID)
    assert registered is not None
    described = registered.run(
        ChartArgs(recipe=recipe, result=result),
        render_module._UnreadableSource(),
    )
    assert isinstance(described, FigureResult)
    return described


def _out_of_process(drawn: _Drawn, *, unset_salt: bool = False) -> str:
    """The sha256 of a render made by a separate interpreter."""
    payload = {
        "recipe": drawn.recipe.model_dump(mode="json"),
        "result": drawn.result.model_dump(mode="json"),
        "root": str(drawn.root),
        "recipe_path": "recipes/figure.json",
        "operator_id": "labcairn.analysis.grouped_aggregate",
        "unset_salt": unset_salt,
    }
    done = subprocess.run(
        [sys.executable, "-c", _OUT_OF_PROCESS],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, (
        f"the out-of-process render failed with exit {done.returncode}: "
        f"{done.stderr.strip()[-800:]}"
    )
    return done.stdout.strip()


# ---------------------------------------------------------------------------
# The chart operator is a catalogue entry
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_chart_operator_is_in_the_catalogue() -> None:
    """``labcairn.analysis.chart`` is registered, and one id has one spelling.

    The catalogue is built from the implementations' own constants, so the
    entry here **is** the operator's own object rather than a second
    spelling of it.
    """
    from labcairn.analysis import catalog

    registered = catalog.operator_for(CHART_OPERATOR_ID)
    assert registered is not None
    assert registered is render_module.CHART
    assert registered.operator.operator_id == "labcairn.analysis.chart"
    assert registered.operator.operator_version == "1.0.0"
    assert registered.operator.args_model is ChartArgs
    assert registered.operator.result_model is FigureResult


@pytest.mark.unit
def test_the_chart_operator_reads_no_cells() -> None:
    """It describes; it does not compute.

    A reader of the operator contract expects an operator to go and look at
    the data. This one does not, because the data has already been read --
    by the operator whose result it was given. The source it is handed
    **raises** when read, so an operator that started reading cells would
    fail loudly rather than quietly find nothing.
    """
    recipe = _recipe()
    result = _grouped()
    described = _described(recipe, result)
    assert described.values
    assert described.plotted


@pytest.mark.unit
def test_the_chart_operator_carries_the_groups_own_numbers() -> None:
    """The figure's values are the operator's values, one for one."""
    result = _grouped()
    described = _described(_recipe(), result)
    assert [value.value for value in described.values] == [group.value for group in result.groups]
    assert [value.key for value in described.values] == [group.key for group in result.groups]


# ---------------------------------------------------------------------------
# The contract with the run path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_renderer_has_the_shape_the_run_path_is_given() -> None:
    """``prepare()`` and ``render(operator_id, result)``, and nothing else.

    The run path must not import this module, so it is given a renderer of
    this shape; the check is here so that the shape cannot drift without
    somebody noticing.
    """
    import inspect

    renderer = MatplotlibFigureRenderer(
        recipe=_recipe(),
        recipe_ref=_reference(),
        workspace_root=Path(),
    )
    assert isinstance(renderer, FigureRenderer)
    assert list(inspect.signature(renderer.render).parameters) == [
        "operator_id",
        "result",
    ]
    assert list(inspect.signature(renderer.prepare).parameters) == []


def _reference() -> Any:
    """A recipe reference that is never read.

    The renderer checks the recipe file's hash before it draws, and this
    test only inspects the renderer's *shape*, so the reference is a
    placeholder rather than a file that would have to exist.
    """
    from labcairn.analysis.manifest import FileRef

    return FileRef(relative_path="recipes/figure.json", content_sha256="a" * 64)


@pytest.mark.unit
def test_a_result_that_is_not_a_table_is_not_a_figure(tmp_path: Path) -> None:
    """A scalar statistic is not something a figure can be drawn from.

    The run path asks the renderer whether there is a figure to write, and
    the answer for a scalar is ``None`` -- a routine answer, not a refusal.

    The recipe names the **mean**, so the operator id matches and this is
    the *other* ``None``: not "this result is not the figure's" but "this
    result is not a table". A recipe that named the grouped aggregate
    would have been answered by the operator-id check instead, and the
    test would have passed without this one being true.
    """
    from labcairn.analysis.operators.descriptive import MEAN, DescriptiveArgs

    recipe = _recipe(
        operator="labcairn.analysis.mean@1.0.0",
        parameters={},
        columns=("value",),
        x="value",
        y="value",
        by="value",
        of="value",
    )
    source = corpus_source("groups.csv")
    selection = corpus_selection("groups.csv", {"rows": "2-17", "columns": ["value"]})
    scalar = MEAN.run(DescriptiveArgs(selection=selection), source)
    drawn = _drawn(tmp_path, recipe, _grouped())
    drawn.renderer.prepare()
    assert drawn.renderer.render("labcairn.analysis.mean", scalar) is None


@pytest.mark.unit
def test_a_result_from_another_operator_is_not_this_figure(tmp_path: Path) -> None:
    """The recipe names the operator the numbers come from.

    A result from any other operator is not *this* figure's, and the
    renderer's word for that is ``None`` as well -- the run path simply has
    no figure to write.
    """
    recipe = _recipe()
    drawn = _drawn(tmp_path, recipe, _grouped())
    drawn.renderer.prepare()
    assert drawn.renderer.render("labcairn.analysis.mean", drawn.result) is None
    assert drawn.renderer.render("labcairn.analysis.chart", drawn.result) is None


@pytest.mark.unit
def test_a_recipe_whose_file_changed_under_the_renderer_is_refused(
    tmp_path: Path,
) -> None:
    """The renderer re-reads the recipe file and compares its hash.

    A figure drawn from a recipe that has changed since the manifest was
    written is a figure the manifest does not describe, and the manifest is
    the audit trail for the figure's numbers.
    """
    recipe = _recipe()
    result = _grouped()
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    (drawn.root / "recipes" / "figure.json").write_text(
        recipe.canonical_bytes().decode("utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(FigureRefusedError) as caught:
        drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert "changed under the renderer" in str(caught.value)


# ---------------------------------------------------------------------------
# The marks
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_bar_s_height_is_the_groups_statistic() -> None:
    """One bar per group, and its height is the statistic."""
    result = _grouped()
    described = _described(_recipe(mark=Mark.BAR), result)
    axes = _artists(described)
    heights = [patch.get_height() for patch in axes.patches]
    assert heights == [group.value for group in result.groups]


@pytest.mark.unit
def test_a_line_joins_the_statistics_in_the_tables_order() -> None:
    """The line is the table's order, not a sort."""
    result = _grouped()
    described = _described(_recipe(mark=Mark.LINE), result)
    axes = _artists(described)
    (line,) = axes.lines
    assert list(line.get_xdata()) == [0, 1, 2]
    assert list(line.get_ydata()) == [group.value for group in result.groups]


@pytest.mark.unit
def test_a_scatter_is_one_point_per_group() -> None:
    """One point per group, at the group's statistic."""
    result = _grouped()
    described = _described(_recipe(mark=Mark.SCATTER), result)
    axes = _artists(described)
    (collection,) = axes.collections
    offsets = collection.get_offsets()
    assert [float(x) for x in offsets[:, 0]] == [0, 1, 2]
    assert [float(y) for y in offsets[:, 1]] == [group.value for group in result.groups]


@pytest.mark.unit
def test_a_histogram_counts_the_groups_statistics() -> None:
    """The y axis is the count of groups per bin -- the renderer's count.

    A histogram counts the statistics rather than plotting a second
    column, so the counts are derived here and the recipe cannot have
    named them.
    """
    result = _grouped()
    described = _described(_recipe(mark=Mark.HISTOGRAM, x="value", y="count"), result)
    axes = _artists(described)
    counts = [patch.get_height() for patch in axes.patches]
    assert sum(counts) == len(result.groups)
    assert len(counts) == HISTOGRAM_BINS


@pytest.mark.unit
def test_a_group_with_no_statistic_is_not_drawn_as_a_zero(tmp_path: Path) -> None:
    """Undefined is undefined: no bar, and the figure says what happened.

    The corpus's ``missing.csv`` has a group whose cells hold no quantity.
    A figure that drew it as a zero would be stating a number the operator
    never computed.
    """
    recipe = _recipe(caption="The mean of each group.")
    result = _grouped("missing.csv", rows="2-7")
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    data = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert data is not None
    svg = data.decode("utf-8")
    # Two groups, one of which has no statistic: one bar, not two. The
    # bars are the patches filled with the declared data colour.
    assert svg.count('style="fill: #1f77b4"') == 1
    assert "no statistic for group" in svg
    described = _described(recipe, result)
    assert described.plotted == (3.0,)


@pytest.mark.unit
def test_a_line_is_broken_where_a_group_has_no_statistic() -> None:
    """A gap, not a point at zero."""
    recipe = _recipe(mark=Mark.LINE, caption="The mean of each group.")
    result = _grouped("missing.csv", rows="2-7")
    described = _described(recipe, result)
    axes = _artists(described)
    (line,) = axes.lines
    ydata = list(line.get_ydata())
    assert ydata[0] == 3.0
    assert ydata[1] != ydata[1]


@pytest.mark.unit
def test_a_table_with_no_statistic_at_all_is_refused() -> None:
    """Nothing to draw is a refusal, not an empty figure."""
    from labcairn.analysis.operators.grouped import GroupAggregate

    groups = (
        GroupAggregate(
            key="A",
            rows=(2,),
            n_used=0,
            n_empty=1,
            n_absent=0,
            n_invalid=0,
            value=None,
            undefined_reason="the group 'A' holds no value",
            unit=None,
        ),
    )
    selection = _selection(("group", "value"), RowRange(2, 3))
    result = GroupedResult(
        operator_id="labcairn.analysis.grouped_aggregate",
        operator_version="1.0.0",
        aggregate="labcairn.analysis.mean@1.0.0",
        by="group",
        of="value",
        groups=groups,
        n_rows_selected=1,
        n_rows_filtered=0,
        n_rows_excluded=1,
        n_rows_ungrouped=0,
        selection=selection,
    )
    with pytest.raises(FigureRefusedError) as caught:
        _described(_recipe(), result)
    assert "nothing to draw" in str(caught.value)


@pytest.mark.unit
def test_a_histogram_of_one_value_is_refused() -> None:
    """A histogram needs a range, and one distinct value has none."""
    from labcairn.analysis.operators.grouped import GroupAggregate

    groups = (
        GroupAggregate(
            key="A",
            rows=(2,),
            n_used=1,
            n_empty=0,
            n_absent=0,
            n_invalid=0,
            value=4.25,
            undefined_reason=None,
            unit=None,
        ),
    )
    selection = _selection(("group", "value"), RowRange(2, 3))
    result = GroupedResult(
        operator_id="labcairn.analysis.grouped_aggregate",
        operator_version="1.0.0",
        aggregate="labcairn.analysis.mean@1.0.0",
        by="group",
        of="value",
        groups=groups,
        n_rows_selected=1,
        n_rows_filtered=0,
        n_rows_excluded=0,
        n_rows_ungrouped=0,
        selection=selection,
    )
    with pytest.raises(FigureRefusedError) as caught:
        _described(_recipe(mark=Mark.HISTOGRAM, x="value", y="count"), result)
    assert "no range to cut into bins" in str(caught.value)


# ---------------------------------------------------------------------------
# The axes must name the result's columns
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_recipe_whose_x_axis_names_another_column_is_refused() -> None:
    """The x axis is the column the result groups by."""
    result = _grouped()
    recipe = _recipe(x="value", y="value")
    with pytest.raises(FigureRefusedError) as caught:
        _described(recipe, result)
    assert "false heading" in str(caught.value)


@pytest.mark.unit
def test_a_recipe_whose_y_axis_names_another_column_is_refused() -> None:
    """The y axis is the column the statistic was computed over."""
    result = _grouped()
    recipe = _recipe(x="group", y="group")
    with pytest.raises(FigureRefusedError) as caught:
        _described(recipe, result)
    assert "false heading" in str(caught.value)


# ---------------------------------------------------------------------------
# The caption
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_caption_that_states_no_number_is_accepted() -> None:
    """A caption says what is plotted, and that is not a claim about a value."""
    described = _described(_recipe(caption="The mean of each group."), _grouped())
    assert described.caption == "The mean of each group."


@pytest.mark.unit
def test_a_caption_that_states_a_number_the_data_holds_is_accepted() -> None:
    """A number the figure plots is a true statement."""
    described = _described(
        _recipe(caption="Group A has a mean of 4.25."),
        _grouped(),
    )
    assert described.caption == "Group A has a mean of 4.25."


@pytest.mark.unit
def test_a_caption_that_states_a_number_the_data_does_not_hold_is_refused() -> None:
    """A caption that states a number the figure does not plot is refused.

    The caption is prose the author wrote, and prose can state a number
    that is not in the figure. It is a false statement printed next to the
    figure, and the renderer is the last thing that could notice.
    """
    with pytest.raises(FigureRefusedError) as caught:
        _described(_recipe(caption="The mean is 4.0."), _grouped())
    assert "4.0" in str(caught.value)
    assert "false statement" in str(caught.value)


@pytest.mark.unit
def test_a_caption_that_states_a_number_in_another_unit_is_refused() -> None:
    """``kg`` against ``g`` is a disagreement, not a conversion.

    The number is one the figure plots -- group B's mean is 4.3 -- and the
    unit it is given is not the one the data carries.
    """
    result = _grouped("units.csv", rows=[2, 3, 4, 5])
    with pytest.raises(FigureRefusedError) as caught:
        _described(_recipe(caption="The mean is 4.3 g."), result)
    message = str(caught.value)
    assert "'g'" in message
    assert "'kg'" in message


@pytest.mark.unit
def test_a_caption_that_states_a_number_in_the_data_s_own_unit_is_accepted() -> None:
    """The same number, in the unit the data carries."""
    result = _grouped("units.csv", rows=[2, 3, 4, 5])
    described = _described(_recipe(caption="The mean is 4.3 kg."), result)
    assert described.caption == "The mean is 4.3 kg."


@pytest.mark.unit
def test_an_interpretation_is_not_checked_for_numbers() -> None:
    """An interpretation is a claim, and is never machine-verified.

    ADR-0004 A10 says so, and checking half of an interpretation would be
    a half-verification of the one thing the project says is never
    verified.
    """
    described = _described(
        _recipe(interpretation="The differences are meaningful."),
        _grouped(),
    )
    assert described.interpretation == "The differences are meaningful."


# ---------------------------------------------------------------------------
# The declared units
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_header_that_declares_a_unit_and_a_recipe_that_declares_another_is_refused() -> None:
    """A conflict, refused, naming both tokens.

    The column is called ``value (kg)``, so its **header** declares
    kilogrammes, and the recipe's axis label declares grammes. The two are
    compared as written and never converted, so the figure is refused.
    """
    recipe = _recipe(
        columns=("group", "value (kg)"),
        x="group",
        y="value (kg)",
        y_label="mean (g)",
        of="value (kg)",
    )
    result = _result((_group("A", 4.25),), of="value (kg)")
    with pytest.raises(FigureRefusedError) as caught:
        _described(recipe, result)
    message = str(caught.value)
    assert "'kg'" in message
    assert "'g'" in message


@pytest.mark.unit
def test_a_header_that_declares_a_unit_and_a_recipe_that_declares_the_same_one_is_accepted() -> (
    None
):
    """The same unit on both sides is not a conflict."""
    recipe = _recipe(
        columns=("group", "value (kg)"),
        x="group",
        y="value (kg)",
        y_label="mean (kg)",
        of="value (kg)",
    )
    result = _result((_group("A", 4.25),), of="value (kg)")
    described = _described(recipe, result)
    assert described.y_label == "mean (kg)"


@pytest.mark.unit
def test_a_header_that_declares_no_unit_and_a_recipe_that_declares_one_is_not_a_conflict() -> None:
    """Saying something where the other side says nothing is not a conflict."""
    recipe = _recipe(y_label="mean (kg)")
    described = _described(recipe, _grouped())
    assert described.y_label == "mean (kg)"


@pytest.mark.unit
def test_a_header_whose_parenthesised_text_has_whitespace_declares_nothing() -> None:
    """``result (see table 2)`` declares no unit.

    Treating the words after a number as a unit is the mistake C3's own
    docstring refuses to make, and ``declared_unit_for`` already draws that
    line; this checks the renderer uses it rather than a second rule.
    """
    from labcairn.analysis.units import declared_unit_for

    assert declared_unit_for("result (see table 2)") is None
    recipe = _recipe(y_label="mean (kg)")
    described = _described(recipe, _grouped())
    assert described.y_label == "mean (kg)"


@pytest.mark.unit
def test_a_recipe_whose_axis_label_contradicts_the_data_s_unit_is_refused() -> None:
    """A figure labelled in one unit over data in another is a false label."""
    result = _grouped("units.csv", rows=[2, 3, 4, 5])
    with pytest.raises(FigureRefusedError) as caught:
        _described(_recipe(y_label="mean (g)"), result)
    message = str(caught.value)
    assert "'g'" in message
    assert "'kg'" in message


@pytest.mark.unit
def test_a_recipe_that_declares_no_unit_at_all_draws() -> None:
    """Saying nothing is allowed."""
    described = _described(_recipe(y_label="mean"), _grouped())
    assert described.y_label == "mean"


@pytest.mark.unit
def test_groups_carrying_two_unit_tokens_are_refused() -> None:
    """One axis carries one unit.

    The corpus's ``units.csv`` holds a group in kilogrammes and a group in
    grammes. A figure whose bars are in two units at once says something
    the data does not say.
    """
    result = _grouped("units.csv", rows="2-7")
    with pytest.raises(FigureRefusedError) as caught:
        _described(_recipe(), result)
    assert "'g'" in str(caught.value)
    assert "'kg'" in str(caught.value)


# ---------------------------------------------------------------------------
# The interpretation's marker
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_an_interpretation_carries_the_not_machine_verified_marker(tmp_path: Path) -> None:
    """The marker is the renderer's, so it cannot be left out by forgetting."""
    recipe = _recipe(interpretation="Group A leads.")
    result = _grouped()
    svg = _svg(tmp_path, recipe, result)
    assert "Group A leads." in svg
    assert INTERPRETATION_MARKER in svg
    assert "interpretation not machine-verified" in svg


@pytest.mark.unit
def test_a_recipe_with_no_interpretation_carries_no_marker(tmp_path: Path) -> None:
    """A caption saying what is plotted is not an interpretation.

    Marking it as one would be a lie about the figure, so the marker
    appears only when there is an interpretation to mark.
    """
    recipe = _recipe(interpretation=None)
    result = _grouped()
    svg = _svg(tmp_path, recipe, result)
    assert INTERPRETATION_MARKER not in svg
    assert "not machine-verified" not in svg


# ---------------------------------------------------------------------------
# Untrusted text
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_group_name_that_looks_like_a_script_is_escaped(tmp_path: Path) -> None:
    """Untrusted text is data, and the SVG must not carry a script element.

    A group name is imported text and ends up in the SVG. An SVG embedded
    in an HTML report is a script context, and the escaping is only safe if
    it holds at the source.
    """
    from labcairn.analysis.operators.grouped import GroupAggregate

    hostile = "<script>alert(1)</script>"
    groups = (
        GroupAggregate(
            key=hostile,
            rows=(2,),
            n_used=1,
            n_empty=0,
            n_absent=0,
            n_invalid=0,
            value=4.25,
            undefined_reason=None,
            unit=None,
        ),
    )
    selection = _selection(("group", "value"), RowRange(2, 3))
    result = GroupedResult(
        operator_id="labcairn.analysis.grouped_aggregate",
        operator_version="1.0.0",
        aggregate="labcairn.analysis.mean@1.0.0",
        by="group",
        of="value",
        groups=groups,
        n_rows_selected=1,
        n_rows_filtered=0,
        n_rows_excluded=0,
        n_rows_ungrouped=0,
        selection=selection,
    )
    recipe = _recipe(caption="The mean of each group.")
    svg = _svg(tmp_path, recipe, result)
    assert "<script" not in svg
    assert "</script>" not in svg
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in svg


@pytest.mark.unit
def test_a_caption_that_looks_like_a_script_is_escaped(tmp_path: Path) -> None:
    """The caption is text too, and it is untrusted in the same way."""
    hostile = "<script>alert('caption')</script>"
    recipe = _recipe(caption=f"The mean of each group. {hostile}")
    result = _grouped()
    svg = _svg(tmp_path, recipe, result)
    assert "<script" not in svg
    assert "&lt;script&gt;" in svg


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_two_svg_renders_in_one_process_are_byte_identical(tmp_path: Path) -> None:
    """The date is the within-process control.

    Two renders a second apart get different creation dates unless the
    date is suppressed, and this is the property that would break.
    """
    recipe = _recipe()
    result = _grouped()
    first = _drawn(tmp_path, recipe, result)
    first.renderer.prepare()
    second = _drawn(tmp_path, recipe, result)
    second.renderer.prepare()
    one = first.renderer.render("labcairn.analysis.grouped_aggregate", result)
    two = second.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert one is not None
    assert two is not None
    assert one == two


@pytest.mark.unit
def test_two_png_renders_in_one_process_are_byte_identical(tmp_path: Path) -> None:
    """PNG needs neither control, and it is identical all the same."""
    recipe = _recipe(figure_format=FigureFormat.PNG)
    result = _grouped()
    first = _drawn(tmp_path, recipe, result)
    first.renderer.prepare()
    second = _drawn(tmp_path, recipe, result)
    second.renderer.prepare()
    one = first.renderer.render("labcairn.analysis.grouped_aggregate", result)
    two = second.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert one is not None
    assert two is not None
    assert one == two


@pytest.mark.unit
def test_a_render_in_another_process_has_the_same_bytes(tmp_path: Path) -> None:
    """The salt is the cross-process control.

    Within one process the salt is constant, so a test that rendered twice
    in one process could not see it at all. This one renders in a separate
    interpreter, where matplotlib would otherwise generate a fresh random
    salt and the element ids would differ.
    """
    recipe = _recipe()
    result = _grouped()
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    here = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert here is not None
    there = _out_of_process(drawn)
    assert hashlib.sha256(here).hexdigest() == there


@pytest.mark.unit
def test_a_png_render_in_another_process_has_the_same_bytes(tmp_path: Path) -> None:
    """And the same for a PNG, even with the salt unset.

    The salt governs the SVG's element ids. A PNG has no element ids, so
    the control does not apply to it -- which is worth checking, because a
    renderer that applied the SVG rule to both formats would be claiming a
    control it had not measured.
    """
    recipe = _recipe(figure_format=FigureFormat.PNG)
    result = _grouped()
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    here = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert here is not None
    there = _out_of_process(drawn, unset_salt=True)
    assert hashlib.sha256(here).hexdigest() == there


@pytest.mark.unit
def test_the_svg_carries_no_creation_date(tmp_path: Path) -> None:
    """The date is suppressed, and the SVG says so by not having one."""
    svg = _svg(tmp_path, _recipe(), _grouped())
    assert "<dc:date>" not in svg
    assert "dc:date" not in svg


@pytest.mark.unit
def test_the_png_carries_no_creation_date(tmp_path: Path) -> None:
    """matplotlib's PNG metadata carries a constant ``Software`` and no date.

    So the PNG needs no date control, and this is the fact that says so:
    the absence is in the file, not in the renderer's discretion.
    """
    recipe = _recipe(figure_format=FigureFormat.PNG)
    result = _grouped()
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    data = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert data is not None
    assert b"Date" not in data
    assert b"Software" in data


@pytest.mark.unit
def test_the_figure_size_is_fixed(tmp_path: Path) -> None:
    """The size is a declared constant, and the SVG declares it.

    A size nobody wrote down would be a decision nobody made, and the
    manifest's environment fingerprint has no field for it -- so the size
    is published here and the SVG states it in points.
    """
    svg = _svg(tmp_path, _recipe(), _grouped())
    assert f'width="{int(FIGURE_SIZE[0] * 72)}pt"' in svg
    assert f'height="{int(FIGURE_SIZE[1] * 72)}pt"' in svg


@pytest.mark.unit
def test_the_png_is_written_at_the_recipe_s_dpi(tmp_path: Path) -> None:
    """The dpi is the recipe's, and the PNG's pixels say so.

    The PNG's header carries the pixel dimensions, so the resolution the
    figure was written at is observable in the file rather than only in
    the recipe.
    """
    recipe = _recipe(figure_format=FigureFormat.PNG, dpi=200)
    result = _grouped()
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    data = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert data is not None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    assert width == int(FIGURE_SIZE[0] * 200)
    assert height == int(FIGURE_SIZE[1] * 200)


@pytest.mark.unit
def test_an_ambient_matplotlibrc_cannot_change_the_bytes(tmp_path: Path) -> None:
    """The declared settings win over whatever the ambient configuration says.

    This is ADR-0012's own open question -- *"nobody has run a render with
    a hostile ``matplotlibrc`` in place to confirm the declared values win.
    T07 owns that measurement"* -- and the hostile file here changes the
    size, the font, the resolution, the save box and the salt. A render
    that ignored the declaration would come out different.
    """
    recipe = _recipe()
    result = _grouped()
    drawn = _drawn(tmp_path, recipe, result)
    drawn.renderer.prepare()
    here = drawn.renderer.render("labcairn.analysis.grouped_aggregate", result)
    assert here is not None

    hostile = MPL_CONFIG_DIR / "matplotlibrc"
    hostile.write_text(
        "figure.figsize : 12.0, 12.0\n"
        "font.family : cmr10\n"
        "font.size : 22\n"
        "savefig.dpi : 33\n"
        "savefig.bbox : tight\n"
        "svg.hashsalt : hostile\n",
        encoding="utf-8",
    )
    try:
        there = _out_of_process(drawn)
    finally:
        hostile.unlink(missing_ok=True)
    assert hashlib.sha256(here).hexdigest() == there


@pytest.mark.unit
def test_the_environment_the_manifest_records_is_the_declared_one() -> None:
    """The fingerprint reads the salt and the fonts from the live process.

    So the renderer has to put them there **before** the fingerprint is
    taken, and the fingerprint has to say what the renderer declared.
    """
    drawn = MatplotlibFigureRenderer(
        recipe=_recipe(),
        recipe_ref=_reference(),
        workspace_root=Path(),
    )
    drawn.prepare()
    environment = current_environment()
    assert environment.svg_hashsalt == SVG_HASHSALT
    assert environment.font_families == ("DejaVu Sans",)
    assert environment.matplotlib_version


@pytest.mark.unit
def test_the_backend_is_selected_rather_than_inherited() -> None:
    """``Agg``, always, and never whatever the session happened to have."""
    import matplotlib

    drawn = MatplotlibFigureRenderer(
        recipe=_recipe(),
        recipe_ref=_reference(),
        workspace_root=Path(),
    )
    drawn.prepare()
    assert matplotlib.get_backend().lower() == "agg"
    assert os.environ["MPLBACKEND"] == "Agg"
    assert os.environ["MPLCONFIGDIR"] == str(MPL_CONFIG_DIR)


@pytest.mark.unit
def test_the_declared_settings_are_hashed() -> None:
    """The declaration is published with a digest of it.

    The manifest's environment fingerprint has no field for the render
    settings, so a reader who wants to know what a figure was drawn under
    can check the digest instead of trusting the code that drew it.
    """
    assert hashlib.sha256(RC_PARAMS_SOURCE.encode("utf-8")).hexdigest() == RC_PARAMS_SHA256
    assert "svg.hashsalt" in RC_PARAMS_SOURCE
    assert SVG_HASHSALT in RC_PARAMS_SOURCE


@pytest.mark.unit
def test_matplotlib_accepts_every_line_of_the_declared_settings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nothing in the declared file is rejected.

    A **declared setting that is not in force** is worse than no declared
    setting: it is a claim the bytes do not keep, and the digest above
    would then be a digest of a file that is partly in effect and partly
    not. matplotlib reads an rcParams value up to the first ``#``, so a
    value carrying hex colours has to be quoted -- and when it is not,
    matplotlib rejects the fragment with a warning and keeps its own
    default, silently.

    So this checks the two halves: that matplotlib's parser accepted
    every line, and that the values it read are the ones declared.
    """
    with caplog.at_level(logging.WARNING, logger="matplotlib"):
        drawn = MatplotlibFigureRenderer(
            recipe=_recipe(),
            recipe_ref=_reference(),
            workspace_root=Path(),
        )
        drawn.prepare()
    rejected = [
        record.getMessage() for record in caplog.records if "Bad value" in record.getMessage()
    ]
    assert not rejected, (
        f"matplotlib rejected a line of the declared settings: {rejected}. A "
        f"declared setting that is not in force is a claim the bytes do not "
        f"keep."
    )


@pytest.mark.unit
def test_the_declared_colour_cycle_is_the_one_in_force() -> None:
    """The colours the figure uses are the declared ones.

    The cycle is declared so that a colour is not an unrecorded input. It
    is checked **in force** rather than declared, because a declared
    value that matplotlib's parser threw away would leave matplotlib's own
    default in its place and the figure's colours would not be the
    declared ones.
    """
    import matplotlib

    drawn = MatplotlibFigureRenderer(
        recipe=_recipe(),
        recipe_ref=_reference(),
        workspace_root=Path(),
    )
    drawn.prepare()
    assert [entry["color"] for entry in matplotlib.rcParams["axes.prop_cycle"]] == [
        "#1f77b4",
        "#ff7f0e",
        "#9467bd",
        "#2ca02c",
    ]


# ---------------------------------------------------------------------------
# The models
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_figure_result_is_a_closed_model() -> None:
    """No extra keys, and the values agree with their reasons."""
    assert FigureResult.model_config["extra"] == "forbid"
    assert FigureValue.model_config["extra"] == "forbid"
    with pytest.raises(ValueError, match="hides an unknown"):
        FigureValue(key="A", value=1.0, undefined_reason="no value")


@pytest.mark.unit
def test_the_chart_operator_is_a_registered_operator() -> None:
    """It has the shape the catalogue expects of an operator."""
    operator: Operator[ChartArgs, FigureResult] = render_module.CHART.operator
    assert operator.args_model is ChartArgs
    assert operator.result_model is FigureResult
    assert issubclass(ChartArgs, OperatorArgs)
    assert isinstance(render_module.CHART, RegisteredOperator)


@pytest.mark.unit
def test_the_chart_operator_s_summary_is_about_what_it_does() -> None:
    """A person reads this line when deciding whether to allow the run."""
    summary = render_module.CHART.operator.summary
    assert summary.strip()
    assert "recipe" in summary


@pytest.mark.unit
def test_the_values_the_figure_plots_are_the_values_the_operator_computed() -> None:
    """The one number that matters, stated once more on its own."""
    result = _grouped()
    described = _described(_recipe(), result)
    expected = tuple(group.value for group in result.groups if group.value is not None)
    assert described.plotted == expected
    assert len(described.values) == len(result.groups)


@pytest.mark.unit
def test_the_source_the_chart_operator_is_handed_refuses_to_be_read() -> None:
    """A source that raises, so an operator that read cells would fail loudly."""
    source = render_module._UnreadableSource()
    with pytest.raises(FigureRefusedError):
        source.text_at(None)  # type: ignore[arg-type]
    with pytest.raises(FigureRefusedError):
        source.rows()
    with pytest.raises(FigureRefusedError):
        _ = source.records_blank_cells


@pytest.mark.unit
def test_the_cell_source_protocol_is_what_the_operator_is_handed() -> None:
    """The unreadable source answers the cell source's three questions.

    ``ValueSource`` is a Protocol and is not runtime-checkable, so the
    check is on the methods themselves rather than on an ``isinstance``.
    """
    source = render_module._UnreadableSource()
    assert callable(source.text_at)
    assert callable(source.rows)
    assert isinstance(type(source).records_blank_cells, property)
