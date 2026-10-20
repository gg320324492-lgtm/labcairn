"""Charts: the recipe that is the editable source, and the renderer.

This package holds the two halves of a figure, and they are kept apart on
purpose. :mod:`labcairn.analysis.chart.recipe` is the **editable source** --
a JSON document a person writes by hand -- and
:mod:`labcairn.analysis.chart.render` (LC-P1-10 T07) is the renderer that
draws it.

The split is the point. A hand-editable script that is then executed is code
execution, and Phase 1 does not promise an OS-level sandbox
(``docs/ARCHITECTURE.md``), so a restricted runner would be a new escape
surface. A recipe is not a program: it names a registered operator, a
selection, an encoding and an output, and there is nothing in it to execute.

The names exported here are the package's, and the two halves keep their
own names and their own purposes: the recipe is the document a person edits,
and the renderer is the code that draws it. Exporting the renderer beside
the recipe does not make it part of that document -- a recipe still names an
operator, a selection, an encoding and an output, and there is still nothing
in it to execute.
"""

from __future__ import annotations

from labcairn.analysis.chart.recipe import (
    DERIVED_COUNT_MARKS,
    MAX_DPI,
    ChartRecipe,
    DataRecipe,
    Encoding,
    FigureFormat,
    Mark,
    Output,
    RecipeRefusedError,
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

__all__ = [
    "CHART_OPERATOR_ID",
    "DERIVED_COUNT_MARKS",
    "FIGURE_SIZE",
    "HISTOGRAM_BINS",
    "INTERPRETATION_MARKER",
    "MAX_DPI",
    "MPL_CONFIG_DIR",
    "RC_PARAMS_SHA256",
    "RC_PARAMS_SOURCE",
    "SVG_HASHSALT",
    "ChartArgs",
    "ChartRecipe",
    "DataRecipe",
    "Encoding",
    "FigureFormat",
    "FigureRefusedError",
    "FigureResult",
    "FigureValue",
    "Mark",
    "MatplotlibFigureRenderer",
    "Output",
    "RecipeRefusedError",
    "SelectionSpec",
]
