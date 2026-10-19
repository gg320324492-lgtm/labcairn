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

The names exported here are the recipe's. The renderer's are imported from
its own module, because a renderer is not part of the document a person
edits, and mixing the two would suggest that it is.
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

__all__ = [
    "DERIVED_COUNT_MARKS",
    "MAX_DPI",
    "ChartRecipe",
    "DataRecipe",
    "Encoding",
    "FigureFormat",
    "Mark",
    "Output",
    "RecipeRefusedError",
    "SelectionSpec",
]
