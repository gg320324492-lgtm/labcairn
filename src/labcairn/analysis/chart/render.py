"""The renderer: a figure, drawn from a recipe and a vetted operator's result.

Two things live here, and they are kept together because the second one is
what makes the first one mean something.

**The chart operator** is a catalogue entry --
``labcairn.analysis.chart@1.0.0`` -- whose arguments are the recipe and the
operator's result, and whose result is a **figure result**: a closed-shape
description of what is to be drawn. It computes nothing and reads no cells;
it *describes*. The reason it exists at all is that the work order's
*"a vetted chart operator renders"* (the task breakdown's §1.4.2) has to be
literally true: the set of things that can draw a figure is **code** rather
than a convention, and the renderer dispatches to the catalogue's own entry
rather than to a private function.

**The renderer** takes that description and draws it, deterministically, in
matplotlib. Its rules are short, and each of them is a refusal rather than a
degradation:

* a result that is not a **table** is not a figure, and the renderer's word
  for that is ``None``;
* a result from an operator other than the one the recipe names is not
  *this* figure, and that too is ``None``;
* everything else -- a recipe whose axes name columns the result does not
  have, a mark the table's shape cannot honour, a caption that states a
  number the figure does not plot, a recipe whose units contradict the data's
  own units, a recipe file that changed under the renderer -- is a
  **refusal**: an exception that names what is wrong.

The numbers are the operator's
-----------------------------
The renderer is given the operator's **result object** and plots it. It does
not re-read the file and it does not re-implement the aggregate, so the
figure's numbers and the operator's numbers cannot drift apart: there is
only one of them. A group whose value is ``None`` has **no statistic** -- it
is undefined, never zero -- so the renderer draws no bar for it, breaks the
line there, and says in the figure what happened.

The determinism controls, and which of them is which
----------------------------------------------------
ADR-0012 measured matplotlib's behaviour, and the two controls are **not
interchangeable**:

* the **creation date** is written into the SVG metadata, and it governs
  renders **within one process** -- two renders a second apart get different
  dates, and suppressing the date is what makes them agree;
* the **salt** (``svg.hashsalt``) governs the element ids and so governs
  renders **across processes** -- left unset, matplotlib generates a fresh
  random salt per interpreter, so a test that renders twice in one process
  cannot see the salt at all.

**PNG needs neither control**, and the reason is measured rather than
assumed: matplotlib's PNG metadata carries a constant ``Software`` string and
**no date at all**, so two PNG renders are already byte-identical, in one
process and across two. A renderer that applied the SVG rule to both formats
would be doing work for a format that does not need it -- and, worse, would
be claiming a control it had not measured.

The other controls are pinned here too: the **backend** is ``Agg`` and is
selected explicitly rather than inherited; the **figure size**, the **dpi**
and ``bbox_inches`` are fixed; ``MPLCONFIGDIR`` is pinned and the font cache
is built there once; and the **rcParams come from a declared, hashed
defaults file** (:data:`RC_PARAMS_SOURCE`), because an ambient
``matplotlibrc`` is an input nobody put in the manifest, and an unrecorded
input is an input the reproducibility claim cannot cover.

The pinned directory is **shared**, and that is a second thing these
controls have to answer. Every process on the machine writes the declared
settings there and reads them back, so a write that truncates before it
writes leaves a window in which another process reads a file that holds
nothing -- and an rc file with no settings in it is an rc file whose salt
fell back to matplotlib's default, which is two renders of one recipe that
are not byte-identical. The files are therefore **put into place whole**:
the bytes go to a temporary file beside the target and are moved onto it
with :func:`os.replace`, which is atomic within a volume. A reader sees the
whole settings or the whole of what was there before, never half of either.

The claim is byte-identity **inside one recorded environment**, and never
across machines: a different machine may resolve different fonts. The
environment fingerprint in the manifest is what makes "identical inputs"
mean something.

The layout is measured, not guessed
-----------------------------------
The figure's text starts **below the axes' tick labels and axis label**,
and where that is is **measured**: the axes' tight bounding box is taken
after a draw, so the labels are where matplotlib actually put them. A
constant is right for one label and wrong for the next, and a caption
drawn across the tick labels is a caption nobody can read -- which is the
acceptance clause's "charts match data and captions" failing on the
figure itself. The measurement is deterministic: it is a function of the
labels and the fonts, and the fonts are part of the recorded environment.

What the manifest's environment does not cover
-----------------------------------------------
The renderer's declared drawing parameters -- the figure's size, the
histogram's bin count, and the digest of the declared settings -- are
published as module constants and are **not** carried by the manifest's
environment fingerprint, so a reader comparing two manifests that say the
same environment cannot tell from the manifests alone why the bytes
differ.
"""

from __future__ import annotations

import io
import math
import os
import re
import tempfile
import textwrap
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, NamedTuple, cast

from pydantic import BaseModel, ConfigDict, model_validator

from labcairn.analysis.chart.recipe import ChartRecipe, FigureFormat, Mark
from labcairn.analysis.manifest import FileRef, read_recipe
from labcairn.analysis.operators import (
    TABULAR_LOCATOR_KINDS,
    Operator,
    OperatorArgs,
    RegisteredOperator,
    parse_operator_reference,
)
from labcairn.analysis.operators.grouped import GroupedResult
from labcairn.analysis.units import declared_unit_for
from labcairn.analysis.values import CellAddress, ValueSource
from labcairn.core.ids import new_id
from labcairn.sources.primitives import NonEmptyText

__all__ = [
    "CHART_OPERATOR_ID",
    "FIGURE_SIZE",
    "HISTOGRAM_BINS",
    "INTERPRETATION_MARKER",
    "MPL_CONFIG_DIR",
    "RC_PARAMS_SHA256",
    "RC_PARAMS_SOURCE",
    "SVG_HASHSALT",
    "ChartArgs",
    "FigureRefusedError",
    "FigureResult",
    "FigureValue",
    "MatplotlibFigureRenderer",
]


class FigureRefusedError(RuntimeError):
    """This figure cannot be drawn, and saying why is the whole answer.

    A refusal rather than a figure with something missing from it. A figure
    drawn from a recipe the renderer could not honour would be showing
    something the author did not write down, and a reader of the figure has
    no way to tell which part of it was meant.
    """


#: The chart operator's id. One constant, so the spelling has exactly one
#: home, and the catalogue quotes it rather than writing it out.
CHART_OPERATOR_ID: Final[str] = "labcairn.analysis.chart"

#: The salt matplotlib uses for the SVG element ids.
#:
#: Fixed, and fixed **for the cross-process reason**: left unset, matplotlib
#: generates a fresh random salt per interpreter, so two renders in two
#: processes differ even with the creation date suppressed. Within one
#: process the salt is constant, which is why a test that renders twice in
#: one process cannot observe this control at all.
SVG_HASHSALT: Final[str] = "labcairn-analysis-figure"

#: The render settings LabCairn declares, as a ``matplotlibrc`` document.
#:
#: **Declared** rather than ambient, and the reason is ADR-0012's: an
#: ambient ``matplotlibrc`` is an input nobody put in the manifest, and an
#: unrecorded input is an input the reproducibility claim cannot cover.
#: :meth:`MatplotlibFigureRenderer.prepare` applies this file over
#: matplotlib's own defaults, so a hostile ``matplotlibrc`` in the ambient
#: configuration cannot survive it.
#:
#: Every value here is one this project has an opinion about, and each of
#: them is a decision rather than an inheritance:
#:
#: ``backend``
#:     ``Agg``, selected explicitly. Never inherited: a session in which
#:     something else imported pyplot first may already have a backend.
#: ``svg.hashsalt``
#:     :data:`SVG_HASHSALT`. The cross-process control.
#: ``savefig.bbox``
#:     ``standard``. ``bbox_inches`` is left unset at the call site, and
#:     this is what makes "left unset" mean unset rather than "whatever the
#:     ambient configuration said".
#: ``savefig.dpi``
#:     ``figure``, so the resolution is the recipe's and never the
#:     ambient one's. The size is not here at all: the renderer passes it
#:     explicitly, and :data:`FIGURE_SIZE` is its one spelling.
#: ``font.family``
#:     ``DejaVu Sans``, which matplotlib bundles. A font that ships with the
#:     library is a font that does not depend on what the machine happens to
#:     have installed, and the manifest's fingerprint records this name.
#: ``axes.prop_cycle``
#:     The colours, spelled out. A colour cycle inherited from whatever the
#:     ambient configuration said would be an unrecorded input like any
#:     other. The value is **quoted**, and that is not decoration: matplotlib
#:     reads an unquoted value up to the first ``#``, so a cycle of hex
#:     colours written plainly is read as the empty fragment before the
#:     first colour, rejected with a warning, and silently replaced by
#:     matplotlib's own default. A declared setting that is not in force is
#:     worse than no declared setting, because it is a claim the bytes do
#:     not keep -- and the digest below would then be a digest of a file
#:     that is partly in effect and partly not.
#: ``text.usetex``
#:     ``False``. A LaTeX render would depend on a LaTeX installation.
RC_PARAMS_SOURCE: Final[str] = """\
# LabCairn's declared render settings. See RC_PARAMS_SOURCE's docstring.
backend                    : Agg
figure.dpi                 : 100
figure.facecolor           : white
figure.autolayout          : False
figure.constrained_layout.use : False
savefig.dpi                : figure
savefig.bbox               : standard
savefig.pad_inches         : 0.1
savefig.facecolor          : white
savefig.edgecolor          : auto
savefig.transparent        : False
font.family                : DejaVu Sans
font.sans-serif            : DejaVu Sans
font.size                  : 10
text.usetex                : False
text.antialiased           : True
axes.unicode_minus         : False
axes.grid                  : False
axes.prop_cycle            : "cycler('color', ['#1f77b4', '#ff7f0e', '#9467bd', '#2ca02c'])"
svg.hashsalt               : labcairn-analysis-figure
svg.fonttype               : path
agg.path.chunksize         : 0
path.simplify              : True
"""

#: The hash of the declared render settings.
#:
#: The point of a *hashed* declaration is that a reader can check the
#: settings a figure was drawn under without trusting the code that drew it.
#: The manifest's environment fingerprint has no field for it (T08's
#: ``RenderEnvironment`` names four), so it is published here instead, and
#: :data:`RC_PARAMS_SOURCE` is the thing it is a hash of.
#:
#: It is **written down** rather than computed, so that changing the
#: settings without saying so is a failure rather than a silence: the test
#: suite compares the two, and a settings file that has drifted from its
#: own digest fails there.
RC_PARAMS_SHA256: Final[str] = "4445af10222192a326d7d76a703698605d2564b54b17d8246cd728cc141f9701"

#: Where matplotlib's configuration and its font cache live.
#:
#: Pinned, because both the ambient ``matplotlibrc`` and the font cache are
#: inputs, and an input at an unrecorded location is an input the
#: reproducibility claim cannot cover.
#:
#: Pinned **does not mean private**: the directory is shared by every
#: process on the machine, so what is written into it is written where
#: another process may be reading it at that very moment. That is what the
#: writing here is careful about -- see :func:`_write_through_a_temporary_file`.
MPL_CONFIG_DIR: Final[Path] = Path(tempfile.gettempdir()) / "labcairn-matplotlib"

#: How many times a file is put into place -- or read back -- before the
#: attempt gives up, and how long it waits between attempts.
#:
#: On Windows a file that another process has open **cannot be replaced**:
#: the rename is refused while the reader holds it. The other side of the
#: same rule bites too: while a replacement is under way the file is marked
#: for deletion, and an open of it in that moment is refused as well. So
#: both the write and the read wait for the other process rather than
#: failing a render over a file that is being shared on purpose.
_REPLACE_ATTEMPTS: Final[int] = 10
_REPLACE_PAUSE: Final[float] = 0.005

#: The figure's size, in inches.
#:
#: Fixed, and not carried by the recipe: the recipe's output section names
#: a format and a dpi, and a size nobody wrote down would be a decision
#: nobody made. The size is published here so that a manifest can record
#: it -- T08's environment fingerprint has no field for it, and a fingerprint
#: that does not cover the size does not cover the bytes.
FIGURE_SIZE: Final[tuple[float, float]] = (6.0, 4.0)

#: How many bins a histogram is cut into.
#:
#: Fixed, for the same reason the size is: a default would be a decision
#: nobody made, and a histogram's bin count changes its bytes.
HISTOGRAM_BINS: Final[int] = 10

#: The marker an interpretation carries.
#:
#: ADR-0004 A10 says an interpretation is **never machine-verified**, so one
#: rendered into a figure has to say so. The marker is in the renderer's
#: hands rather than the author's, precisely so that it cannot be left out
#: by forgetting -- and a recipe with **no** interpretation carries no
#: marker, because a caption saying what is plotted is not an interpretation.
INTERPRETATION_MARKER: Final[str] = "[interpretation not machine-verified]"

#: Where the axes sit.
#:
#: Fixed, and set with ``add_axes`` rather than left to a layout engine, so
#: that the plot has a declared home and the layout does not depend on
#: which strings happen to be in it. The axes are **shortened** when the
#: figure's text needs the room (see :func:`_text_top`), and nothing else
#: about them moves.
_AXES_RECT: Final[tuple[float, float, float, float]] = (0.10, 0.36, 0.86, 0.56)

#: Where the figure's text sits: its left margin, its line step, its size.
#:
#: The text's **top** is not among them, because it is not a constant. It
#: is measured -- the axes' tight bounding box is taken after a draw, so
#: the tick labels and the axis label are where they actually are, and the
#: text goes below them. A constant would be right for one label and
#: wrong for the next, and a caption drawn across the tick labels is a
#: caption nobody can read: the acceptance clause's "charts match data and
#: captions" failing on the figure itself.
_TEXT_LEFT: Final[float] = 0.02
_TEXT_STEP: Final[float] = 0.030
_TEXT_SIZE: Final[float] = 7.0
_TEXT_WIDTH: Final[int] = 96

#: The gap between the axes' labels and the figure's text.
_TEXT_CLEARANCE: Final[float] = 0.02

#: The space kept below the figure's last line of text.
_TEXT_MARGIN: Final[float] = 0.02

#: The smallest the plot may be, so that a long caption cannot squeeze it
#: out of the figure altogether.
_MIN_AXES_HEIGHT: Final[float] = 0.20

#: How close a caption's number has to be to a plotted value to be *that*
#: value.
#:
#: Not exact equality, because a float computed by an aggregate is not
#: always the float a reader would write down: the mean of 0.1 and 0.2 is
#: 0.15000000000000002, and a caption that says 0.15 is not lying. The
#: tolerance is the corpus's own.
_NUMBER_TOLERANCE: Final[float] = 1e-12

#: A number in a caption, and the unit token that may follow it.
#:
#: The shape is the one :mod:`labcairn.sources.quantity` reads, for the same
#: reason: a number is a number and at most one token. The lookbehind keeps
#: a number from being found inside a word ("v1.2" is not a number), and
#: the lookahead keeps "1.2.3" -- a version -- from being read as two
#: numbers.
_CAPTION_NUMBER: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w.])"
    r"(?P<number>[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:[eE][-+]?\d+)?)"
    r"(?!\.\d)"
    r"\s*"
    r"(?P<unit>%|°?[A-Za-z]+(?:/[A-Za-z]+)?)?"
)

#: The suffixes that make a number an ordinal rather than a quantity.
#:
#: "the 3rd group" states the number 3, not the number 3 of something, and
#: reading "rd" as a unit token would make a caption that says nothing
#: about units look like one that says something wrong about them.
_ORDINAL_SUFFIXES: Final[frozenset[str]] = frozenset({"st", "nd", "rd", "th"})


class ChartArgs(OperatorArgs):
    """What the chart operator takes: the recipe, and the result it describes.

    The recipe is the figure's editable source and the result is the table
    the figure is drawn from. Both are required, and neither is optional in
    the sense of "may be left out": a chart operator with no recipe has no
    encoding, and one with no result has no numbers.
    """

    #: The recipe the figure is drawn from.
    recipe: ChartRecipe
    #: The result the figure's numbers come from.
    result: GroupedResult


class FigureValue(BaseModel):
    """One group, and what the figure draws for it.

    ``value`` is ``None`` **exactly** when ``undefined_reason`` is set, the
    same rule the operator's own result carries: a value with no reason
    hides an unknown, and a reason with no value says nothing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The group key, as written in the cell that named it.
    key: str
    #: The group's statistic, or ``None`` when it is undefined.
    value: float | None
    #: Why the statistic is undefined. Required when ``value`` is ``None``.
    undefined_reason: str | None = None
    #: The unit the group's used cells carry, when they carry one.
    unit: str | None = None

    @model_validator(mode="after")
    def _a_value_and_a_reason_come_together(self) -> FigureValue:
        if (self.value is None) != (self.undefined_reason is not None):
            raise ValueError(
                f"the figure's value for group {self.key!r} is "
                f"{self.value!r} with reason {self.undefined_reason!r}. A value "
                f"with no reason hides an unknown, and a reason with no value "
                f"says nothing."
            )
        return self


class FigureResult(BaseModel):
    """What a figure is, in closed form.

    This is the chart operator's output, and it is a **description** rather
    than an image: the marks, the labels, the title, the caption, the
    interpretation if there is one, the values, and the output settings. The
    renderer draws it and nothing else, so the set of things that can be
    drawn is a closed model rather than a convention.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The mark. One of the recipe's closed set.
    mark: Mark
    #: The figure's title.
    title: NonEmptyText
    #: The x axis's label.
    x_label: NonEmptyText
    #: The y axis's label.
    y_label: NonEmptyText
    #: What is plotted. The author's own words.
    caption: NonEmptyText
    #: A claim about what the figure means, if the recipe carries one.
    #:
    #: It is carried **raw**. The marker that says it is not
    #: machine-verified is added by the renderer, so that it cannot be left
    #: out by forgetting.
    interpretation: NonEmptyText | None = None
    #: One entry per group, in the table's order.
    values: tuple[FigureValue, ...]
    #: The format the figure is written in.
    format: FigureFormat
    #: The resolution the figure is written at.
    dpi: int

    @property
    def plotted(self) -> tuple[float, ...]:
        """The values the figure draws, and only those.

        A group with no statistic is not one of them: it is undefined, never
        zero, and a figure that drew it as a zero would be stating a number
        the operator never computed.
        """
        return tuple(value.value for value in self.values if value.value is not None)


def describe(args: ChartArgs, source: ValueSource) -> FigureResult:
    """The figure the recipe and the result describe.

    **The source is ignored.** This operator reads no cells: it computes
    nothing and describes what the *result* holds, which is why the
    renderer can hand it a source that refuses to be read. A reader of the
    operator contract expects an operator to go and look at the data, and
    the reason this one does not is that the data has already been read --
    by the operator whose result it was given. The figure's numbers are
    that operator's numbers, and there is exactly one reading of the file.
    """
    recipe = args.recipe
    result = args.result

    _check_the_axes_name_the_result(recipe, result)
    _check_the_units_agree(recipe, result)
    values = tuple(
        FigureValue(
            key=group.key,
            value=group.value,
            undefined_reason=group.undefined_reason,
            unit=group.unit,
        )
        for group in result.groups
    )
    _check_the_mark_can_be_honoured(recipe.encoding.mark, values)
    _check_the_caption_states_only_plotted_numbers(recipe.encoding.caption, values)

    return FigureResult(
        mark=recipe.encoding.mark,
        title=recipe.encoding.title,
        x_label=recipe.encoding.x_label,
        y_label=recipe.encoding.y_label,
        caption=recipe.encoding.caption,
        interpretation=recipe.encoding.interpretation,
        values=values,
        format=recipe.output.format,
        dpi=recipe.output.dpi,
    )


_CHART_OPERATOR: Final[Operator[ChartArgs, FigureResult]] = Operator(
    operator_id=CHART_OPERATOR_ID,
    operator_version="1.0.0",
    args_model=ChartArgs,
    result_model=FigureResult,
    accepted_locator_kinds=TABULAR_LOCATOR_KINDS,
    summary="a figure described from a recipe and a vetted operator's result",
)

#: The registered chart operator.
#:
#: The catalogue holds it among the operators it registers, so the renderer
#: dispatches to the catalogue's own entry rather than to a private
#: function, and "a vetted chart operator renders" is a fact about the code
#: rather than about a convention.
CHART: Final[RegisteredOperator[ChartArgs, FigureResult]] = RegisteredOperator(
    operator=_CHART_OPERATOR, run=describe
)


class _UnreadableSource:
    """A cell source that refuses to be read.

    The chart operator computes nothing, so the renderer has no source to
    give it. Handing it one that raises is better than handing it one that
    answers, because an operator that started reading cells would then fail
    loudly instead of quietly finding nothing.
    """

    def text_at(self, address: CellAddress) -> str | None:
        raise FigureRefusedError(
            "the chart operator read a cell. It computes nothing: the figure's "
            "numbers are the result it was given, and a chart operator that "
            "goes to the file for them would be a second reading of the data "
            "that could disagree with the first."
        )

    def rows(self) -> tuple[int, ...]:
        raise FigureRefusedError("the chart operator asked for the source's rows.")

    @property
    def records_blank_cells(self) -> bool:
        raise FigureRefusedError("the chart operator asked about the source's blanks.")


class MatplotlibFigureRenderer:
    """Draws a figure from a recipe and the operator's result.

    The recipe is a **constructor argument** rather than something the run
    path carries, because the recipe is a figure-side input: the run path
    records it by path and hash without interpreting it, and the figure's
    own drawing needs to know what the figure is about. The recipe file's
    reference is a constructor argument too, so that the renderer can
    re-check that the file has not changed under it -- a renderer that drew
    a figure from a recipe the manifest does not describe would be drawing
    something nobody recorded.
    """

    def __init__(
        self,
        *,
        recipe: ChartRecipe,
        recipe_ref: FileRef,
        workspace_root: Path,
    ) -> None:
        self._recipe = recipe
        self._recipe_ref = recipe_ref
        self._workspace_root = workspace_root

    @property
    def recipe(self) -> ChartRecipe:
        """The recipe this renderer draws from."""
        return self._recipe

    def prepare(self) -> None:
        """Put the render environment into its declared state.

        It has to run **before** anything reads the environment, because the
        manifest's fingerprint reads the salt, the fonts and the platform
        from the live process: a fingerprint taken before the environment
        was put into its declared state would record the ambient one.

        The declared settings are **put into place whole**: they are
        replaced rather than rewritten, so that a process preparing the
        environment at the same moment as this one cannot read a file that
        holds half of them. See :func:`_write_the_settings`.
        """
        os.environ["MPLBACKEND"] = "Agg"
        os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)
        MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        import matplotlib

        matplotlib.use("Agg")
        # The ambient configuration cannot survive this: rcdefaults restores
        # matplotlib's own shipped defaults, and the declared file is
        # applied over them. The second use() is because the declared file
        # names a backend too, and the backend is the one thing this
        # renderer never inherits.
        matplotlib.rcdefaults()
        declared = MPL_CONFIG_DIR / "labcairn-matplotlibrc"
        _write_the_settings(declared)
        _apply_the_settings(matplotlib, declared)
        matplotlib.use("Agg")
        _build_the_font_cache(matplotlib)

    def render(self, operator_id: str, result: BaseModel) -> bytes | None:
        """The figure's bytes, or ``None`` when this result is not a figure.

        ``None`` means exactly one thing: *this result does not produce a
        figure*. Two cases, and both are routine rather than defects:

        * the result came from an operator the recipe does not name, so it
          is not **this** figure's numbers; and
        * the result is not a **table** -- a scalar statistic, say -- and a
          scalar is not something a figure can be drawn from.

        Everything else is a refusal, because everything else is a defect in
        the inputs rather than a fact about the result.
        """
        data_operator, _version = parse_operator_reference(self._recipe.data.operator)
        if operator_id != data_operator:
            return None
        if not isinstance(result, GroupedResult):
            return None

        self._check_the_recipe_has_not_changed()
        figure = self._describe(result)
        return self._draw(figure)

    def _check_the_recipe_has_not_changed(self) -> None:
        """The recipe file is still the one the manifest recorded.

        The renderer holds the recipe's bytes' hash beside the recipe, and
        this re-reads the file to compare them. A figure drawn from a
        recipe that has changed since the manifest was written is a figure
        the manifest does not describe, and the manifest is the audit trail
        for the figure's numbers.
        """
        current = read_recipe(self._workspace_root, self._recipe_ref.relative_path)
        if current.content_sha256 == self._recipe_ref.content_sha256:
            return
        raise FigureRefusedError(
            f"the recipe file {self._recipe_ref.relative_path!r} has changed "
            f"under the renderer: it now hashes to {current.content_sha256} and "
            f"the renderer was built for bytes that hash to "
            f"{self._recipe_ref.content_sha256}. A figure drawn from a recipe "
            f"the manifest does not describe is a figure nobody can check."
        )

    def _describe(self, result: GroupedResult) -> FigureResult:
        """The figure, described by the catalogue's chart operator.

        The dispatch goes through the catalogue rather than to
        :func:`describe` directly, so that the thing that draws a figure is
        the registered operator and not a private function that happens to
        agree with it.
        """
        from labcairn.analysis import catalog

        registered = catalog.operator_for(CHART_OPERATOR_ID)
        if registered is None:
            raise FigureRefusedError(
                f"the chart operator {CHART_OPERATOR_ID!r} is not in the "
                f"catalogue, so this build has no way to describe a figure. A "
                f"renderer that drew one anyway would be drawing from a "
                f"convention rather than from a vetted operator."
            )
        args = ChartArgs(recipe=self._recipe, result=result)
        described = registered.run(args, _UnreadableSource())
        return cast(FigureResult, described)

    def _draw(self, figure: FigureResult) -> bytes:
        """The figure's bytes."""
        import matplotlib.pyplot as plt

        canvas = plt.figure(figsize=FIGURE_SIZE, dpi=figure.dpi)
        try:
            _draw_the_figure(canvas, figure)
            buffer = io.BytesIO()
            if figure.format is FigureFormat.SVG:
                # The date is the within-process control, and it is an SVG
                # control: matplotlib's PNG metadata carries no date at all,
                # so a PNG needs neither this nor the salt.
                canvas.savefig(buffer, format="svg", dpi=figure.dpi, metadata={"Date": None})
            else:
                canvas.savefig(buffer, format="png", dpi=figure.dpi)
            return buffer.getvalue()
        finally:
            plt.close(canvas)


def _draw_the_figure(canvas: Any, figure: FigureResult) -> None:
    """The whole figure, on a canvas the caller owns.

    Split out from the renderer's own draw so that the geometry can be
    measured on the canvas the figure was drawn on. A figure's layout is a
    property of the figure, and a test that could not see it could not
    check it.
    """
    axes = canvas.add_axes(_AXES_RECT)
    _draw_the_mark(axes, figure)
    axes.set_xlabel(figure.x_label)
    axes.set_ylabel(figure.y_label)
    axes.set_title(figure.title)
    _draw_the_text(canvas, axes, figure)


def _draw_the_mark(axes: Any, figure: FigureResult) -> None:
    """Draw the mark, from the figure's values and nothing else.

    A group with no statistic is **not** drawn: no bar, no point, and -- for
    a line -- a break in the line rather than a point at zero. The figure's
    text says which groups those were, so the reader is not left guessing
    why a group is missing.
    """
    values = figure.values
    defined = [(index, value) for index, value in enumerate(values) if value.value is not None]
    if figure.mark is Mark.BAR:
        axes.bar([index for index, _ in defined], [value.value for _, value in defined])
        axes.set_xticks(range(len(values)))
        axes.set_xticklabels([value.key for value in values])
    elif figure.mark is Mark.LINE:
        axes.plot(
            [index for index, _ in enumerate(values)],
            [value.value if value.value is not None else math.nan for value in values],
        )
        axes.set_xticks(range(len(values)))
        axes.set_xticklabels([value.key for value in values])
    elif figure.mark is Mark.SCATTER:
        axes.scatter([index for index, _ in defined], [value.value for _, value in defined])
        axes.set_xticks(range(len(values)))
        axes.set_xticklabels([value.key for value in values])
    elif figure.mark is Mark.HISTOGRAM:
        axes.hist([value.value for _, value in defined], bins=HISTOGRAM_BINS)
    else:  # pragma: no cover - the mark is a closed set
        raise FigureRefusedError(
            f"the figure asks for the mark {figure.mark!r}, which this build "
            f"does not implement. A mark outside the closed set is a mark no "
            f"renderer in this build draws."
        )


def _draw_the_text(canvas: Any, axes: Any, figure: FigureResult) -> None:
    """The figure's text: the caption, what happened to the undefined groups,
    and the interpretation with its marker.

    The **marker is added here**, in the renderer, rather than being asked
    of the recipe: ADR-0004 A10 says an interpretation is never
    machine-verified, and a marker that lives in the recipe is a marker that
    can be left out by forgetting. A recipe with no interpretation gets no
    marker, because a caption saying what is plotted is not an
    interpretation and marking it as one would be a lie about the figure.

    The text starts **below the axes' labels**, and where that is is
    **measured** rather than guessed: see :func:`_text_top`.
    """
    lines = _text_lines(figure)
    top = _text_top(canvas, axes, lines)
    for index, line in enumerate(lines):
        canvas.text(
            _TEXT_LEFT,
            top - index * _TEXT_STEP,
            line,
            ha="left",
            va="top",
            fontsize=_TEXT_SIZE,
        )


def _text_lines(figure: FigureResult) -> tuple[str, ...]:
    """The figure's text, one line each.

    The caption, then a line for each group with no statistic, then the
    interpretation with its marker.
    """
    lines: list[str] = list(textwrap.wrap(figure.caption, width=_TEXT_WIDTH))
    for value in figure.values:
        if value.value is None:
            lines.extend(
                textwrap.wrap(
                    f"no statistic for group {value.key!r}: {value.undefined_reason}",
                    width=_TEXT_WIDTH,
                )
            )
    if figure.interpretation is not None:
        lines.extend(
            textwrap.wrap(f"{figure.interpretation} {INTERPRETATION_MARKER}", width=_TEXT_WIDTH)
        )
    return tuple(lines)


def _text_top(canvas: Any, axes: Any, lines: tuple[str, ...]) -> float:
    """Where the figure's text starts, in fractions of the figure's height.

    **Measured, not guessed.** The axes' tight bounding box is taken after
    a draw, so the tick labels and the axis label are where they actually
    are rather than where a constant hoped they would be, and the text
    goes below that box. A constant is right for one label and wrong for
    the next -- and a caption drawn across the tick labels is a caption
    nobody can read.

    If the text does not fit in the space below the labels, the **plot
    gives up the room**: the axes are shortened and the text starts below
    them again. A shorter plot is a legible figure; a caption that runs off
    the page is not.
    """
    top = _label_band_bottom(canvas, axes) - _TEXT_CLEARANCE
    shortfall = _TEXT_MARGIN - (top - len(lines) * _TEXT_STEP)
    if shortfall <= 0:
        return top
    left, bottom, width, height = axes.get_position().bounds
    if height - shortfall < _MIN_AXES_HEIGHT:
        raise FigureRefusedError(
            f"the figure's text needs {len(lines)} line(s), and the plot cannot "
            f"be shortened to make room for them without the figure ceasing to "
            f"be a figure. A caption that runs off the page is a caption nobody "
            f"can read, so the figure is refused rather than drawn badly."
        )
    axes.set_position((left, bottom + shortfall, width, height - shortfall))
    return _label_band_bottom(canvas, axes) - _TEXT_CLEARANCE


def _label_band_bottom(canvas: Any, axes: Any) -> float:
    """Where the band the axes' labels occupy ends, in figure fractions.

    Measured from the axes' tight bounding box -- which is where matplotlib
    puts the tick labels and the axis label, rather than where a constant
    might have guessed.
    """
    canvas.canvas.draw()
    renderer = canvas.canvas.get_renderer()
    box = axes.get_tightbbox(renderer)
    return float(box.transformed(canvas.transFigure.inverted()).y0)


def _check_the_axes_name_the_result(recipe: ChartRecipe, result: GroupedResult) -> None:
    """The recipe's axes name the columns the result has.

    A recipe that says ``x = "region"`` over a result grouped by
    ``"country"`` is asking for an axis the figure does not have, and
    drawing the groups under the wrong heading is a false label.
    """
    encoding = recipe.encoding
    if encoding.mark is Mark.HISTOGRAM:
        # A histogram's x axis is the statistic itself, binned -- not the
        # group column, whose values are names rather than quantities.
        expected_x, expected_y = result.of, None
    else:
        expected_x, expected_y = result.by, result.of
    if encoding.x != expected_x:
        raise FigureRefusedError(
            f"the recipe's x axis names the column {encoding.x!r}, and the "
            f"result groups by {result.by!r} over {result.of!r}. The x axis of "
            f"this figure is the column {expected_x!r}, and a figure whose "
            f"axis names a column the result does not have is a figure with a "
            f"false heading."
        )
    if expected_y is not None and encoding.y != expected_y:
        raise FigureRefusedError(
            f"the recipe's y axis names the column {encoding.y!r}, and the "
            f"statistic was computed over {result.of!r}. The y axis of this "
            f"figure is the column {expected_y!r}, and a figure whose axis "
            f"names a column the result does not have is a figure with a false "
            f"heading."
        )


def _check_the_units_agree(recipe: ChartRecipe, result: GroupedResult) -> None:
    """The recipe's declared units, the columns' declared units and the data's
    own units agree.

    Three places can declare a unit, and they are compared rather than
    reconciled: the column's **header** (``mass (kg)`` declares ``kg``),
    the recipe's **axis label** (``mean (kg)`` declares ``kg``), and the
    **data** (the token the cells' own text carried). Units are compared as
    written and never converted -- ``kg`` against ``g`` is a disagreement,
    not a conversion -- so a disagreement is refused and both tokens are
    named.

    A unit that only one side declares is not a disagreement: a column whose
    cells carry no token leaves the declared unit **unverified**, which is
    the asymmetry C3 keeps everywhere else.

    The **header against the cells** is not this function's to settle: the
    selection refuses that disagreement when it resolves the column, before
    an operator ever sees a value. So the two the renderer compares -- the
    recipe's own declaration against the header's and against the data's --
    are the two the recipe is answerable for, and the renderer's comparison
    of the header against the data is a second opinion rather than the only
    one.
    """
    data_units = sorted({group.unit for group in result.groups if group.unit is not None})
    if len(data_units) > 1:
        listed = ", ".join(repr(token) for token in data_units)
        raise FigureRefusedError(
            f"the groups carry {len(data_units)} different unit tokens: "
            f"{listed}. One axis carries one unit, and a figure whose bars are "
            f"in two units at once says something the data does not say."
        )
    data_unit = data_units[0] if data_units else None

    for label, column, carries_data in _axes_of(recipe, result):
        label_unit = declared_unit_for(label)
        column_unit = declared_unit_for(column) if column is not None else None
        if label_unit is not None and column_unit is not None and label_unit != column_unit:
            raise FigureRefusedError(
                f"the axis label {label!r} declares the unit {label_unit!r} and "
                f"the column {column!r} declares the unit {column_unit!r}. A "
                f"header that declares a unit and a recipe that declares a "
                f"different one is a conflict, and units are compared as "
                f"written and never converted."
            )
        if not carries_data or data_unit is None:
            continue
        for declared in (label_unit, column_unit):
            if declared is not None and declared != data_unit:
                raise FigureRefusedError(
                    f"the axis label {label!r} declares the unit "
                    f"{declared!r} and the data's own cells carry the unit "
                    f"{data_unit!r}. A figure labelled in one unit over data in "
                    f"another is a figure whose label is false, and units are "
                    f"compared as written and never converted."
                )


def _axes_of(
    recipe: ChartRecipe, result: GroupedResult
) -> tuple[tuple[str, str | None, bool], ...]:
    """Each axis: its label, the column it shows, and whether it shows the
    statistic.

    A histogram's y axis is a count the renderer derives, so it has no
    column and no unit to check.
    """
    encoding = recipe.encoding
    if encoding.mark is Mark.HISTOGRAM:
        return ((encoding.x_label, result.of, True), (encoding.y_label, None, False))
    return (
        (encoding.x_label, result.by, False),
        (encoding.y_label, result.of, True),
    )


def _check_the_mark_can_be_honoured(mark: Mark, values: tuple[FigureValue, ...]) -> None:
    """The table's shape can carry the mark.

    A figure needs something to draw, and a histogram needs a **range** to
    cut into bins: one distinct value has no range, and the edges numpy
    would make up around it are not "from those values".
    """
    plotted = [value.value for value in values if value.value is not None]
    if not plotted:
        raise FigureRefusedError(
            f"the table has {len(values)} group(s) and not one of them has a "
            f"statistic, so there is nothing to draw. A group with no value is "
            f"not a group of zero, and a figure of zeroes would be a number "
            f"the operator never computed."
        )
    if mark is Mark.HISTOGRAM:
        distinct = set(plotted)
        if len(distinct) < 2:
            raise FigureRefusedError(
                f"a histogram of {len(plotted)} value(s) with "
                f"{len(distinct)} distinct value(s) has no range to cut into "
                f"bins. The bin edges come from the values, and one distinct "
                f"value has no edges to come from."
            )


def _check_the_caption_states_only_plotted_numbers(
    caption: str, values: tuple[FigureValue, ...]
) -> None:
    """Every number the caption states is one the figure plots.

    A caption is prose the author wrote, and prose can state a number that
    is not in the figure. A caption that says "Mean = 4.0" over data whose
    values hold no 4.0 is a false statement about the figure, printed next
    to it, and this is the last thing that could notice.

    The numbers checked are the **group statistics** the figure is drawn
    from -- the operator's numbers, not a second reading of the file. A
    caption that states no number at all is fine: "Mass by group" states
    none, and saying what is plotted is not the same as claiming a value.

    The **interpretation** is not checked, and deliberately: it is a claim
    about what the figure means, and ADR-0004 A10 says such a claim is
    never machine-verified. Checking half of it would be a half-verification
    of the thing the project says is never verified.
    """
    for stated in _caption_numbers(caption):
        matches = [
            value
            for value in values
            if value.value is not None and _same_number(stated.value, value.value)
        ]
        if not matches:
            plotted = ", ".join(repr(value.value) for value in values if value.value is not None)
            raise FigureRefusedError(
                f"the caption states the number {stated.text!r}, and the figure "
                f"plots {plotted}. A caption that states a number the data does "
                f"not contain is a false statement about the figure."
            )
        if stated.unit is None:
            continue
        units = {value.unit for value in matches}
        if stated.unit in units or None in units:
            continue
        carried = ", ".join(repr(unit) for unit in sorted(units, key=str))
        raise FigureRefusedError(
            f"the caption states the number {stated.text!r} in the unit "
            f"{stated.unit!r}, and the figure plots that number in the unit "
            f"{carried}. Units are compared as written and never converted, so "
            f"a number in a different unit is a disagreement rather than the "
            f"same quantity."
        )


def _same_number(left: float, right: float) -> bool:
    """Whether two numbers are the same number.

    With a tolerance, because a float an aggregate computed is not always
    the float a reader would write down: the mean of 0.1 and 0.2 is
    0.15000000000000002, and a caption that says 0.15 is not lying.
    """
    return math.isclose(left, right, rel_tol=_NUMBER_TOLERANCE, abs_tol=_NUMBER_TOLERANCE)


class _StatedNumber(NamedTuple):
    """One number a caption states."""

    #: The number, as written.
    value: float
    #: The unit it carries, or ``None`` when it carries none.
    unit: str | None
    #: The number as the caption wrote it, for the refusal's wording.
    text: str


def _caption_numbers(caption: str) -> tuple[_StatedNumber, ...]:
    """The numbers a caption states, with the unit each one carries."""
    stated: list[_StatedNumber] = []
    for match in _CAPTION_NUMBER.finditer(caption):
        text = match.group("number")
        value = float(text.replace(",", ""))
        unit = match.group("unit")
        if unit is not None and not _is_a_unit_token(match, unit):
            unit = None
        stated.append(_StatedNumber(value=value, unit=unit, text=text))
    return tuple(stated)


def _is_a_unit_token(match: re.Match[str], unit: str) -> bool:
    """Whether the token after a number is a unit or part of the word.

    A number glued to letters is usually an ordinal -- "3rd" -- and an
    ordinal is a number and not a quantity. Everything else that follows a
    number is read as a unit, which is the strict reading: a caption that
    says "3 kg" over data in grams is a disagreement, and a rule that
    guessed which words were units would guess wrong about half of them.
    """
    if unit == "%":
        return True
    glued = match.start("unit") == match.end("number")
    return not (glued and unit.lower() in _ORDINAL_SUFFIXES)


def _build_the_font_cache(matplotlib: Any) -> None:
    """Build matplotlib's font cache in the pinned configuration directory.

    The cache is where matplotlib remembers which fonts it found, and its
    location is part of what makes a render environment-dependent: an
    inherited cache is an inherited input. Building it once in the pinned
    directory means the render reads a font list this project chose where
    to keep, rather than one left wherever an earlier session put it.

    It is put into place **whole**, the same way the declared settings are,
    because it is the same shared directory: a reader that caught the file
    half-written would find something that is not a font list, and
    matplotlib answers that by scanning every font on the machine again.
    (matplotlib writes this file itself when it is missing, and it writes
    it in place; what is claimed here is about the write this function
    makes.)
    """
    from matplotlib import font_manager

    cachedir = Path(matplotlib.get_cachedir())
    cachedir.mkdir(parents=True, exist_ok=True)
    path = cachedir / f"fontlist-v{font_manager.FontManager.__version__}.json"
    if path.exists():
        return
    _write_through_a_temporary_file(
        path,
        lambda temporary: font_manager.json_dump(font_manager.FontManager(), temporary),
    )


def _write_the_settings(path: Path) -> None:
    """The declared settings, in the recorded file, whole or not at all.

    The bytes go to a temporary file in the **same directory** and are moved
    into place with :func:`os.replace`, which is atomic within a volume.
    Same-directory matters: :func:`os.replace` is atomic only within a
    volume, so a temporary file in the system temp directory would silently
    give up the guarantee. This is the shape
    :meth:`labcairn.workspace.outputs.TaskOutputArea.write` uses, for the
    same reason -- minus its ``fsync``, because these settings are written
    down again from the declaration on the next run, so surviving a power
    loss is not a claim this file makes.

    Why the render environment needs it at all: the pinned directory is
    **shared by every process on the machine**, and each of them writes the
    declared settings there and reads them back to apply them. A write that
    truncates first leaves a window -- a few microseconds wide -- in which
    the file holds nothing at all, and a process that reads it inside that
    window gets an rc file with no settings in it. ``svg.hashsalt`` then
    falls back to matplotlib's default, the figure's element ids are salted
    with a fresh random value, and two renders of one recipe stop being
    byte-identical. Neither process can explain the difference, because
    each of them did exactly what it was told.

    A replacement has no such window: a reader sees the whole of the
    settings or the whole of what was there before, never half of either.

    The settings are written **as bytes**, so the file holds the declaration
    exactly as :data:`RC_PARAMS_SOURCE` spells it -- the line endings
    included. Writing them as text would let the platform's newline
    translation into the file, and the file's digest would then no longer
    be the digest the project published.
    """

    def write(temporary: Path) -> None:
        with temporary.open("xb") as handle:
            handle.write(RC_PARAMS_SOURCE.encode("utf-8"))
            handle.flush()

    _write_through_a_temporary_file(path, write)


def _write_through_a_temporary_file(path: Path, write: Callable[[Path], None]) -> None:
    """Put a file into place by way of a temporary file beside it.

    The temporary file is a **sibling** of the target rather than a file in
    the system temp directory: :func:`os.replace` is atomic only within a
    volume, and a temporary file elsewhere would give up that guarantee
    silently. The temporary file is removed if anything goes wrong, so a
    failed write leaves neither a half-written file nor a stray one.
    """
    temporary = path.parent / f".lc-render-{new_id().hex}.tmp"
    try:
        write(temporary)
        _waiting_for_the_other_process(lambda: temporary.replace(path))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _waiting_for_the_other_process(action: Callable[[], object]) -> None:
    """Run *action*, waiting out a process that holds the shared file.

    Windows refuses to replace a file that another process has open, and
    refuses an open of a file whose replacement is under way. The file in
    the pinned directory is **shared on purpose** -- every process on the
    machine reads the declared settings out of it -- so the refusal is not
    a defect to report but a rule to wait out: the process on the other
    side is reading a file that is about to be replaced, so it is nearly
    done.

    The action is retried, so it has to be one that can be run twice. Both
    of the ones it wraps are: a replacement of the same bytes, and a read
    of a file that holds the same bytes either way.
    """
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            action()
            return
        except PermissionError:
            if attempt + 1 == _REPLACE_ATTEMPTS:
                raise
            time.sleep(_REPLACE_PAUSE)


def _apply_the_settings(matplotlib: Any, path: Path) -> None:
    """Put the recorded settings into force.

    The settings are read from the **recorded file** rather than from the
    declaration in this module, so that what is in force is what the file
    says -- and the file's digest is the digest the project published. The
    read is retried for the same reason the write is: another process may
    be replacing that file at this moment.
    """
    _waiting_for_the_other_process(lambda: matplotlib.rc_file(str(path)))
