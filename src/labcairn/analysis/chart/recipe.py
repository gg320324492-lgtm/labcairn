"""The chart recipe: the editable source of a figure.

A figure in LC-P1-10 is drawn from a **recipe** -- a JSON document that a
person edits by hand -- and the recipe is the whole of what the figure is.
There is no script beside it, and no way to run one. That is what makes the
work order's *"Explicitly no general-purpose model-authored code execution"*
satisfiable rather than aspirational (the task breakdown's §1.4.2): a recipe
names an operator from the catalogue, a selection, an encoding and an output,
and the renderer (LC-P1-10 T07) draws it.

Three parts, and no others
--------------------------
**data** is an operator, that operator's parameters, and the selection the
parameters apply to. The figure's numbers are therefore *a vetted operator's
output* rather than a second reading of the file, which is what makes "the
chart matches the data" a property of the code and not a coincidence of two
readers happening to agree.

**encoding** is the mark, the two axes, the title, the axis labels, the
caption and, optionally, an interpretation.

**output** is the format and the dpi.

The caption and the interpretation are different fields
-------------------------------------------------------
A **caption** says what is plotted. An **interpretation** states a claim about
what it means. They are separate fields, and the reason is ADR-0004 A10: an
interpretation is never machine-verified, so one that is rendered into a
figure has to carry a marker -- and the marker is the *renderer's* job, not
the author's, so it cannot be left out by forgetting.

So a recipe that has an interpretation names one and the renderer marks it,
and a recipe that has none carries no marker at all, because a caption saying
what is plotted is not an interpretation and marking it as one would be a lie
about the figure. Putting both in one field would put that decision in the
author's hands, which is precisely where A10 does not want it.

A recipe is not a program
-------------------------
There is no expression language, no template, no import, and no way to name
anything that is not a registered operator, a declared column, or a literal
value. The closed set of marks, operators and columns *is* the whole
language.

Refuse rather than degrade
---------------------------
A recipe that names an operator this build does not implement, a mark outside
the closed set, a column the selection does not have, or parameters the
operator does not accept is **refused**. It is not a warning, and it is not a
field that is quietly dropped: a figure drawn from a recipe that had been
partly understood would be showing something nobody wrote down.

Two kinds of refusal, and the difference is the remedy
------------------------------------------------------
A **shape** problem -- an unknown mark, an unknown key, a number where a
string belongs -- is a :class:`pydantic.ValidationError`, because the
document does not fit the schema at all. A **semantic** refusal -- an
unregistered operator, a stale version, a column the selection does not have
-- is a :class:`RecipeRefusedError`, because the document is well formed and
this build will not do what it says. The distinction is the one
:mod:`labcairn.core.schema` draws for a schema version: the two have
different repairs, so they are not the same exception.

Frozen and canonical
--------------------
The recipe is frozen and its serialisation is canonical, because its bytes
are hashed into the manifest and a document that serialises two ways cannot
be compared with itself. The canonical form is the project's own
:meth:`~labcairn.core.schema.LabCairnModel.json_canonical` -- sorted keys, no
incidental whitespace, UTF-8 -- and the hash is taken over those bytes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from labcairn.analysis.operators import OperatorIdError, parse_operator_reference
from labcairn.analysis.selection import MissingPolicy, RowFilter, RowRange, RowSet, Selection
from labcairn.core.schema import LabCairnModel
from labcairn.sources.primitives import ContentHash, NonEmptyText, WorkspaceRelativePath

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


class Mark(StrEnum):
    """The marks a recipe may ask for.

    Closed, and closed by enumeration rather than by a rule that could be
    relaxed: a mark that is not in this set is a mark no renderer in this
    build implements, and a recipe that names one is refused rather than
    approximated by whichever mark happened to be nearest.
    """

    #: One bar per category, from a category and a value.
    BAR = "bar"
    #: One point per category, joined in the order the categories come.
    LINE = "line"
    #: One point per observation.
    SCATTER = "scatter"
    #: The distribution of one column, counted into bins.
    HISTOGRAM = "histogram"


class FigureFormat(StrEnum):
    """The formats a figure may be written in.

    Two, because those are the two the work order's determinism claim covers:
    an SVG is text and can be diffed, and a PNG is a bitmap whose bytes depend
    on the renderer. Anything else would be a third thing to pin.
    """

    SVG = "svg"
    PNG = "png"


#: The marks whose y axis is a **count the renderer derives** from the binned
#: x, rather than a column of the source.
#:
#: Every other mark plots two columns of the selection, so its y is one of
#: them and the recipe can be checked against the selection. A histogram
#: counts a column rather than plotting a second one, so its y is the name
#: the renderer gives the count it derives -- and that name is not a column
#: of the source, and pretending otherwise would have the recipe checked
#: against a set it was never meant to be in.
DERIVED_COUNT_MARKS: Final[frozenset[Mark]] = frozenset({Mark.HISTOGRAM})

#: The largest dpi a recipe may ask for.
#:
#: A resource bound rather than an aesthetic one, and enforced here rather
#: than at the renderer, because a recipe is the one document a person edits
#: by hand and a hand-edited number is exactly how a four-figure bitmap gets
#: asked for. The cost is that a recipe needing more than this is refused
#: rather than drawn.
MAX_DPI: Final[int] = 600


class RecipeRefusedError(RuntimeError):
    """A well-formed recipe that names something this build will not do.

    A refusal, not a flag, and not a
    :class:`pydantic.ValidationError`: the document fits the schema and says
    something this build refuses to carry out. The two have different
    repairs -- a malformed document is corrected, a refused one is not -- so
    they are not the same exception. This one is a
    :class:`RuntimeError` rather than a :class:`ValueError` for the same
    reason: pydantic converts a ``ValueError`` raised in a validator into a
    ``ValidationError``, and the type would be lost.
    """


class _Part(BaseModel):
    """The base for the recipe's four parts.

    The settings the persisted contracts use, without a
    ``schema_version``. The recipe is **one** versioned document, and its
    parts are fields of it rather than documents of their own -- a document
    that carried a version in each of its four sections would be carrying
    four versions of one thing, and a person editing it by hand would have
    to keep four of them in step.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


#: The three row specs, one adapter each.
#:
#: They are disjoint -- a range has boundaries, a set has rows, a filter has
#: a column, an operator and a value -- so the first one that accepts a
#: written spec is the one that was meant, and each can be written back out
#: in the form it is stored in.
_ROW_SPEC_ADAPTERS: Final[tuple[TypeAdapter[Any], ...]] = (
    TypeAdapter(RowRange),
    TypeAdapter(RowSet),
    TypeAdapter(RowFilter),
)

#: The content-hash shape, checked where a recipe's selection is bound to a
#: source.
_CONTENT_HASH: Final[TypeAdapter[Any]] = TypeAdapter(ContentHash)

#: The non-empty-text shape, checked for the same reason.
_NON_EMPTY_TEXT: Final[TypeAdapter[Any]] = TypeAdapter(NonEmptyText)

#: The source a stand-in selection carries.
#:
#: A recipe's selection is not bound to a source until the run path resolves
#: it, so the parameters are checked against a selection that has the
#: recipe's own shape and a source that does not exist. The stand-in is
#: thrown away, and it exists so that the *operator* -- not this module -- is
#: the one that says which parameters it accepts.
_UNRESOLVED_SOURCE_ID: Final[str] = "unresolved"
_UNRESOLVED_CONTENT_HASH: Final[str] = "0" * 64


class SelectionSpec(_Part):
    """Which cells of which file, as a recipe writes it down.

    This is the analysis layer's selection **before it is resolved**: the
    source is a path rather than a source id and a content hash, because the
    hash belongs to the file and the run path is what reads the file. The
    vocabulary is otherwise the selection's own -- the columns are named,
    the rows are a range, a set or a filter, and the missing-value policy is
    declared rather than defaulted -- so there is one answer to "which cells"
    and not two.

    The rows are written in the form they are stored in, and a row spec that
    is not in that form is refused. Pydantic would otherwise read ``"2"`` as
    the number 2 and say nothing about it, and a recipe is the one document
    in this project that a person writes by hand, so a number written as a
    word is a likely mistake rather than an exotic one.
    """

    #: The file, workspace-relative and POSIX-separated. A path that escapes
    #: the workspace is refused rather than resolved.
    source: WorkspaceRelativePath
    #: The columns, by header text. Never by index.
    columns: tuple[NonEmptyText, ...]
    #: The rows, in one of the three ways the selection names them.
    rows: RowRange | RowSet | RowFilter
    #: What to do about a cell that yields no quantity. Declared, not
    #: defaulted: a default is a silent decision about the data.
    missing: MissingPolicy

    @model_validator(mode="before")
    @classmethod
    def _the_rows_are_written_as_they_are_stored(cls, raw: Any) -> Any:
        """Refuse a row spec that is not already in its stored form.

        The check is a comparison rather than a rule about which fields are
        numbers, so it holds whatever shape the row vocabulary takes: the
        written spec and the stored spec have to be the same document.
        """
        if isinstance(raw, dict) and "rows" in raw:
            _refuse_a_rewritten_row_spec(raw["rows"])
        return raw

    @model_validator(mode="after")
    def _the_columns_are_a_set(self) -> SelectionSpec:
        """No empty set of columns, and no column twice.

        A selection over no columns is a statistic over nothing, and a column
        named twice is one column whose cells would be counted twice. The
        analysis layer's own selection refuses both, and a recipe that
        described one would be describing something the operator cannot run.
        """
        if not self.columns:
            raise RecipeRefusedError(
                "the recipe's selection names no columns. A selection over no "
                "columns is a statistic over nothing."
            )
        if len(set(self.columns)) != len(self.columns):
            repeated = sorted({column for column in self.columns if self.columns.count(column) > 1})
            listed = ", ".join(repr(column) for column in repeated)
            raise RecipeRefusedError(
                f"the recipe's selection repeats a column: {listed}. One column "
                f"twice is one column, and its cells would be counted twice."
            )
        return self

    def to_selection(self, source_id: NonEmptyText, content_sha256: ContentHash) -> Selection:
        """The selection this recipe describes, bound to a resolved source.

        The recipe names a file; the run path (LC-P1-10 T09) resolves that
        file to a source and its content hash, and this is where the two
        halves meet. The hash is checked here rather than trusted, because a
        selection bound to a malformed hash is a selection bound to nothing.
        """
        return Selection(
            source_id=_NON_EMPTY_TEXT.validate_python(source_id),
            content_sha256=_CONTENT_HASH.validate_python(content_sha256),
            columns=self.columns,
            rows=self.rows,
            missing=self.missing,
        )


class DataRecipe(_Part):
    """Where the figure's numbers come from.

    An operator, the parameters that operator takes besides the selection,
    and the selection they apply to. The parameters are checked **by the
    operator's own argument model**, so the question "which parameters does
    this operator accept?" has exactly one answer, and it is the operator's.
    """

    #: The operator, as its reference -- the id and the version quoted
    #: together, ``labcairn.analysis.mean@1.0.0``.
    #:
    #: The version is part of the name because the recipe's bytes are hashed:
    #: a recipe that named only the id would mean something different after a
    #: version bump, and a document whose meaning can change without its
    #: bytes changing cannot be compared with itself.
    operator: str
    #: The operator's other arguments. The selection is not among them; it
    #: is a field of its own.
    parameters: dict[str, JsonValue]
    #: The selection the parameters apply to.
    selection: SelectionSpec

    @model_validator(mode="after")
    def _the_operator_accepts_these_parameters(self) -> DataRecipe:
        """The operator is registered, current, and accepts these parameters.

        Each of the three is a separate refusal because each has a separate
        repair: an unknown id is a typo, a stale version is a recipe written
        against another build, and a rejected parameter is a parameter the
        operator does not take.
        """
        # The import is inside the function rather than at module level: the
        # catalogue holds the chart operator among the ones it registers, and
        # the chart operator's module needs this one for the recipe's types,
        # so a top-level import here would close a cycle. The same remedy
        # ``operators/grouped.py`` uses for the same shape.
        from labcairn.analysis.catalog import operator_for

        operator_id, version = _reference_parts(self.operator)
        registered = operator_for(operator_id)
        if registered is None:
            raise RecipeRefusedError(
                f"the recipe names the operator {operator_id!r}, and this build "
                f"implements no operator with that id. A recipe may only name a "
                f"registered operator, because the figure's numbers are that "
                f"operator's output and nothing else."
            )
        current = registered.operator.operator_version
        if current != version:
            raise RecipeRefusedError(
                f"the recipe names the operator {operator_id!r} at version "
                f"{version!r}, and this build implements version {current!r}. A "
                f"recipe that names one version and runs another says something "
                f"other than what was written down."
            )
        if "selection" in self.parameters:
            raise RecipeRefusedError(
                "the selection is a field of the data recipe of its own, so it "
                "may not also be a parameter. A recipe carrying it twice has "
                "two selections, and only one of them is the one that ran."
            )
        arguments = {**self.parameters, "selection": _stand_in_selection(self.selection)}
        try:
            registered.operator.args_model.model_validate(arguments)
        except ValidationError as exc:
            raise RecipeRefusedError(
                f"the operator {operator_id!r} does not accept these parameters: {_describe(exc)}"
            ) from exc
        return self


class Encoding(_Part):
    """What the figure shows, and what it says about it.

    The mark is one of a closed set; the two axes name columns; the title
    and the axis labels are the text the reader sees; the caption says what
    is plotted; and the interpretation, if there is one, says what it means.
    """

    #: The mark. One of a closed set, and nothing else is a mark.
    mark: Mark
    #: The column on the x axis.
    x: NonEmptyText
    #: The column on the y axis. For a histogram this is the name of the
    #: count the renderer derives, and it is therefore not a column of the
    #: source; see :data:`DERIVED_COUNT_MARKS`.
    y: NonEmptyText
    #: The figure's title.
    title: NonEmptyText
    #: The x axis's label. It may carry a unit the column's name does not.
    x_label: NonEmptyText
    #: The y axis's label, and the same about units.
    y_label: NonEmptyText
    #: What is plotted. Required, and never empty: a figure that does not
    #: say what it shows has not said what it is.
    caption: NonEmptyText
    #: A claim about what the figure means.
    #:
    #: Optional, and separate from the caption, because an interpretation is
    #: never machine-verified (ADR-0004 A10) and the renderer -- not the
    #: author -- is what marks it. Absent means absent: the recipe does not
    #: ask for a marker and the renderer will not add one.
    interpretation: NonEmptyText | None = None


class Output(_Part):
    """What the figure is written as."""

    #: The format. One of a closed set.
    format: FigureFormat
    #: The resolution. Required, because a dpi is a decision somebody made
    #: and a default would be a decision nobody made.
    dpi: Annotated[int, Field(strict=True, ge=1, le=MAX_DPI)]


class ChartRecipe(LabCairnModel):
    """A whole recipe: the data, the encoding and the output.

    This is the editable source of a figure. It is frozen and canonical,
    because its bytes are hashed into the manifest, and it is a closed
    document, because the closed set of marks, operators and columns is the
    whole of what a recipe may say.
    """

    #: Where the numbers come from.
    data: DataRecipe
    #: What the figure shows and says.
    encoding: Encoding
    #: What the figure is written as.
    output: Output

    @model_validator(mode="after")
    def _the_axes_name_columns_the_selection_has(self) -> ChartRecipe:
        """The axes name columns of the selection, or the recipe is refused.

        A column the selection does not have is a column with no data behind
        it, and a figure that drew one would be showing an axis the author
        invented. The one mark whose y is not a column is the one whose y the
        renderer derives.
        """
        columns = self.data.selection.columns
        listed = ", ".join(repr(column) for column in columns)
        if self.encoding.x not in columns:
            raise RecipeRefusedError(
                f"the x axis names the column {self.encoding.x!r}, and the "
                f"selection does not have it. The selection's columns are: "
                f"{listed}."
            )
        if self.encoding.mark not in DERIVED_COUNT_MARKS and self.encoding.y not in columns:
            raise RecipeRefusedError(
                f"the y axis names the column {self.encoding.y!r}, and the "
                f"selection does not have it. The selection's columns are: "
                f"{listed}. A histogram is the one mark whose y axis is a count "
                f"the renderer derives rather than a column of the source."
            )
        return self

    def canonical_bytes(self) -> bytes:
        """The recipe's bytes: the canonical JSON, encoded as UTF-8.

        These are the bytes the manifest hashes. UTF-8 rather than the
        default escaping, because a caption written in the author's own
        characters should be the same document after it is hashed as it was
        before.
        """
        return self.json_canonical().encode("utf-8")


def _reference_parts(reference: str) -> tuple[str, str]:
    """The id and version a reference names, or a refusal.

    The grammar check is the operator contract's own, so the reference has
    one spelling and the recipe does not get a second one.
    """
    try:
        return parse_operator_reference(reference)
    except OperatorIdError as exc:
        raise RecipeRefusedError(
            f"the recipe names the operator {reference!r}, which is not a "
            f"well-formed operator reference. The form is '<operator id>"
            f"@<version>', for example 'labcairn.analysis.mean@1.0.0'."
        ) from exc


def _stand_in_selection(spec: SelectionSpec) -> Selection:
    """A selection with the recipe's shape and a source that does not exist.

    Thrown away after the operator's model has had its say. It carries the
    recipe's own columns, rows and policy, so an operator that checks its
    selection is checked against the recipe's, and only the binding to a
    source is missing.
    """
    return Selection(
        source_id=_UNRESOLVED_SOURCE_ID,
        content_sha256=_UNRESOLVED_CONTENT_HASH,
        columns=spec.columns,
        rows=spec.rows,
        missing=spec.missing,
    )


def _refuse_a_rewritten_row_spec(raw: Any) -> None:
    """Refuse a row spec that is not written in the form it is stored in.

    Pydantic reads a number written as a string as the number, and it says
    nothing about it. A recipe is written by hand, so that is a likely
    mistake rather than an exotic one, and a recipe that had been quietly
    rewritten would be hashed in a form its author never wrote.
    """
    if not isinstance(raw, dict):
        return
    stored = _stored_row_spec(raw)
    if stored != raw:
        raise RecipeRefusedError(
            f"the row specification {raw!r} is not written in the form it is "
            f"stored in, which is {stored!r}. A number written as a word, or a "
            f"value written in a case the vocabulary does not use, is a "
            f"different document from the one that was meant."
        )


def _stored_row_spec(raw: Any) -> Any:
    """The row specification as it is stored, or a refusal.

    The three specs are disjoint, so the first one that accepts the written
    spec is the one that was meant, and what it accepts is what the spec
    looks like once it has been read.
    """
    for adapter in _ROW_SPEC_ADAPTERS:
        try:
            validated = adapter.validate_python(raw)
        except ValidationError:
            continue
        return adapter.dump_python(validated, mode="json")
    raise RecipeRefusedError(
        f"the row specification {raw!r} is not one of the three the selection "
        f"names: a range with a start and an end, a set of rows, or a filter "
        f"with a column, an operator and a value."
    )


def _describe(exc: ValidationError) -> str:
    """What an operator's argument model objected to, in one line.

    The refusal has to **name** what was wrong: a reader told only that the
    parameters were not accepted cannot tell a typo from a parameter that
    does not exist.
    """
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )
