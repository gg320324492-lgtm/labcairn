"""The chart recipe: the editable source of a figure.

A recipe is the one document in LC-P1-10 that a **person** writes by hand,
and everything under test here follows from that. It is JSON, it is closed,
it is canonical, and it names nothing that is not a registered operator, a
declared column, or a literal value.

Four things are under test, and the last two are the ones a reader is most
likely to get wrong:

* the **recipe is a recipe** -- a hand-written document parses, round-trips,
  and serialises to one canonical form whatever order it was written in;
* the **refusals** -- an unregistered operator, a stale version, a parameter
  the operator does not take, and a column the selection does not have are
  all refusals, and none of them is a warning or a dropped field;
* the **caption and the interpretation are different fields** -- a caption
  says what is plotted, an interpretation says what it means, and only the
  second one is ever machine-unverified (ADR-0004 A10);
* the **whole language is closed** -- the serialised recipe holds exactly
  the declared keys and nothing else, which is what makes "there is no
  code-execution surface" a property of the document rather than a promise.

The corpus is the oracle for anything about the data, so the recipe under
test is built over the columns a corpus fixture really carries.
"""

from __future__ import annotations

import copy
import json
from string import Template
from typing import Any

import pytest
from analysis_fixtures import CORPUS_DIR, load_expected, read_table_csv
from pydantic import ValidationError

from labcairn.analysis.catalog import operator_version
from labcairn.analysis.chart.recipe import (
    DERIVED_COUNT_MARKS,
    MAX_DPI,
    ChartRecipe,
    FigureFormat,
    Mark,
    RecipeRefusedError,
)
from labcairn.analysis.selection import MissingPolicy

#: The version this build implements for the operator the recipes under test
#: name. Read from the catalogue rather than written out, so that a version
#: bump is a change to the catalogue and not a change to every test that
#: happens to mention it.
VERSION = operator_version("labcairn.analysis.stdev")
assert VERSION is not None

#: A recipe, written the way a person would write it. The version is
#: substituted so that the document below is a real recipe rather than a
#: template.
RECIPE_TEXT = Template(
    """{
  "data": {
    "operator": "labcairn.analysis.stdev@${version}",
    "parameters": {"ddof": 1},
    "selection": {
      "source": "runs/exp1.csv",
      "columns": ["group", "value"],
      "rows": {"start": 2, "end": 11},
      "missing": "exclude"
    }
  },
  "encoding": {
    "mark": "bar",
    "x": "group",
    "y": "value",
    "title": "Standard deviation over the value column",
    "x_label": "group",
    "y_label": "sample standard deviation",
    "caption": "The sample standard deviation of the value column, over 10 rows.",
    "interpretation": null
  },
  "output": {"format": "svg", "dpi": 200}
}
"""
).substitute(version=VERSION)

#: The same recipe as a mapping, for the tests that change one field.
BASE: dict[str, Any] = json.loads(RECIPE_TEXT)

#: Every key the serialised recipe may hold, by the path it is held at.
#:
#: ``data.parameters`` is not here: which keys an operator's parameters
#: have is the operator's own vocabulary, and the operator's argument model
#: is what decides it. Everything else is this recipe's vocabulary, and it is
#: closed.
ALLOWED_KEYS: dict[str, set[str]] = {
    "": {"data", "encoding", "output", "schema_version"},
    "data": {"operator", "parameters", "selection"},
    "data.selection": {"source", "columns", "rows", "missing"},
    "data.selection.rows": {"start", "end"},
    "encoding": {
        "mark",
        "x",
        "y",
        "title",
        "x_label",
        "y_label",
        "caption",
        "interpretation",
    },
    "output": {"format", "dpi"},
}


def _part(path: str, **changes: Any) -> dict[str, Any]:
    """The base recipe's part at *path*, with the given fields changed.

    The path is dotted, and what comes back replaces the **top** part, so
    ``_part("data.selection", columns=[...])`` returns the whole ``data``
    part with the selection's columns changed. A test that means to change
    one field says where it is changing it.
    """
    parts = path.split(".")
    document = copy.deepcopy(BASE)
    node: dict[str, Any] = document
    for part in parts:
        node = node[part]
    node.update(changes)
    replaced: dict[str, Any] = document[parts[0]]
    return replaced


def _with_extra_key(path: str) -> dict[str, Any]:
    """The base document with an extra key at *path*."""
    document = copy.deepcopy(BASE)
    if path == "":
        document["script"] = "import os"
        return document
    parts = path.split(".")
    node: dict[str, Any] = document
    for part in parts:
        node = node[part]
    node["script"] = "import os"
    return document


def _recipe(**parts: Any) -> ChartRecipe:
    """A recipe built from the base document, with whole parts replaced.

    Each argument replaces one part, so a test that means to change one
    field says which part it is changing and cannot accidentally change
    another.
    """
    document = copy.deepcopy(BASE)
    document.update(parts)
    return ChartRecipe.model_validate(document)


def _keys_at(document: Any, path: str = "") -> dict[str, set[str]]:
    """The key set of every object in a document, by the path it is at."""
    found: dict[str, set[str]] = {}
    if isinstance(document, dict):
        found[path] = set(document)
        for key, value in document.items():
            found.update(_keys_at(value, f"{path}.{key}" if path else key))
    elif isinstance(document, list):
        for value in document:
            found.update(_keys_at(value, f"{path}[]"))
    return found


@pytest.mark.unit
def test_a_hand_written_recipe_is_a_recipe() -> None:
    """The document a person writes is one this build reads.

    Not a Python object: the text above is parsed as JSON, and the recipe
    that comes out is the recipe the manifest will hash. If the two halves
    of the round trip disagreed, the editable source would be a document
    that only a program could produce.
    """
    recipe = ChartRecipe.model_validate_json(RECIPE_TEXT)
    assert recipe.data.operator == f"labcairn.analysis.stdev@{VERSION}"
    assert recipe.data.parameters == {"ddof": 1}
    assert recipe.data.selection.source == "runs/exp1.csv"
    assert recipe.data.selection.columns == ("group", "value")
    assert recipe.encoding.mark is Mark.BAR
    assert recipe.encoding.caption.startswith("The sample standard deviation")
    assert recipe.output.format is FigureFormat.SVG
    assert recipe.output.dpi == 200


@pytest.mark.unit
def test_the_recipe_round_trips_through_its_canonical_form() -> None:
    """Reading the recipe back gives the recipe.

    The canonical form is what the manifest hashes, so if the recipe and its
    own serialisation were different documents, the hash would be of
    something nobody wrote.
    """
    recipe = ChartRecipe.model_validate_json(RECIPE_TEXT)
    assert ChartRecipe.model_validate_json(recipe.json_canonical()) == recipe
    assert recipe.canonical_bytes() == recipe.json_canonical().encode("utf-8")


@pytest.mark.unit
def test_the_canonical_form_is_the_project_s_canonical_json() -> None:
    """The recipe's serialisation is the project's canonical JSON.

    Sorted keys, no incidental whitespace, and no escaping: the convention
    the manifest's digest is defined over. A recipe that serialised any
    other way would hash differently from a recipe that says the same
    thing, and the manifest would then be a statement about whoever wrote
    it rather than about the figure.
    """
    canonical = _recipe().json_canonical()
    assert canonical == json.dumps(
        json.loads(canonical), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


@pytest.mark.unit
def test_the_canonical_form_is_the_same_whatever_order_the_document_was_written_in() -> None:
    """The bytes do not depend on how the author arranged the document.

    A recipe is edited by hand and by machine, and the manifest hashes the
    bytes. If the key order changed the hash, two runs over the same recipe
    would produce two manifests that do not compare equal, and the
    comparison would be a statement about the editor rather than about the
    figure.
    """
    shuffled = json.loads(json.dumps(BASE))
    shuffled = {key: shuffled[key] for key in reversed(list(shuffled))}
    assert ChartRecipe.model_validate(shuffled).canonical_bytes() == _recipe().canonical_bytes()


@pytest.mark.unit
def test_the_canonical_form_keeps_the_characters_the_author_wrote() -> None:
    """A caption in the author's own characters is not escaped away.

    The canonical JSON is UTF-8 and does not escape, and the bytes are the
    UTF-8 encoding of it. A caption written in Greek or in Chinese is the
    same document before and after it is hashed, and the hash is of the
    characters the author typed.
    """
    caption = "La concentration (µg/L) par groupe — 每组浓度"
    recipe = _recipe(encoding=_part("encoding", caption=caption))
    canonical = recipe.json_canonical()
    assert caption in canonical
    assert "\\u" not in canonical
    assert caption.encode("utf-8") in recipe.canonical_bytes()


@pytest.mark.unit
def test_the_recipe_is_frozen() -> None:
    """A recipe does not change after it has been written down.

    The recipe's bytes are hashed, and a model that could be changed between
    the digest being computed and the figure being drawn would make the
    digest decorative. Every part is frozen too: the encoding is where the
    claim lives, and a mutable encoding is a mutable claim.
    """
    recipe = _recipe()
    changed: Any = _part("encoding", caption="another caption")
    with pytest.raises(ValidationError):
        recipe.encoding = changed
    columns: Any = ("value",)
    with pytest.raises(ValidationError):
        recipe.data.selection.columns = columns
    with pytest.raises(ValidationError):
        recipe.output.dpi = 300


@pytest.mark.unit
def test_the_serialised_recipe_holds_exactly_the_declared_keys() -> None:
    """The recipe's whole vocabulary is the declared keys.

    This is what "there is no code-execution surface" means in practice: the
    document has no field that could carry a script, a path to a module, an
    expression, or anything else that could be evaluated. A new field would
    have to be added here as well, which is the point -- it cannot be added
    quietly.
    """
    found = _keys_at(json.loads(_recipe().canonical_bytes()))
    for path, keys in found.items():
        if path.startswith("data.parameters"):
            # The parameters' keys are the operator's vocabulary, and the
            # operator's own argument model is what closes them.
            continue
        assert path in ALLOWED_KEYS, f"the recipe holds an object at {path!r}"
        assert keys == ALLOWED_KEYS[path], f"the keys at {path!r} are not the declared ones"


@pytest.mark.unit
def test_the_recipe_names_the_operator_version_this_build_implements() -> None:
    """The recipe's operator is named with the version that would run.

    A recipe that named only the id would mean something different after a
    version bump, and a document whose meaning can change without its bytes
    changing cannot be compared with itself.
    """
    recipe = _recipe()
    assert recipe.data.operator.endswith(f"@{operator_version('labcairn.analysis.stdev')}")


@pytest.mark.unit
def test_the_recipe_refuses_an_unregistered_operator() -> None:
    """A name this build does not implement is refused, not attempted.

    The catalogue is a constant, so an operator id that is not in it cannot
    be run -- there is no code path that could run it. The recipe says so
    rather than leaving the reader to find out at the first run.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data", operator="labcairn.analysis.smooth@1.0.0"))
    assert "labcairn.analysis.smooth" in str(refusal.value)


@pytest.mark.unit
def test_the_recipe_refuses_an_operator_version_this_build_does_not_implement() -> None:
    """A recipe written against another version is refused.

    Running it and reporting the new version would make the recipe mean
    something other than what it says, and the manifest would then record a
    version the recipe never named.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data", operator="labcairn.analysis.stdev@9.9.9"))
    assert "9.9.9" in str(refusal.value)


@pytest.mark.unit
def test_the_recipe_refuses_an_operator_reference_that_is_not_well_formed() -> None:
    """A reference with no version is not a reference, and the refusal says so.

    The id alone names an operator this build implements, so a refusal that
    blamed the version would point the author at a version they never wrote
    instead of at the missing ``@version``. The grammar is the operator
    contract's own, and the refusal has to name the reference as it was
    written.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data", operator="labcairn.analysis.stdev"))
    message = str(refusal.value)
    assert "not a well-formed operator reference" in message
    assert "labcairn.analysis.stdev" in message
    assert "at version" not in message


@pytest.mark.unit
def test_the_recipe_refuses_a_parameter_the_operator_does_not_accept() -> None:
    """A parameter the operator does not take is refused, and named.

    The operator's own argument model is what decides, so there is one
    answer to "which parameters does this operator take" and it is the
    operator's. The refusal names the offending key, because a reader told
    only that the parameters were not accepted cannot tell a typo from a
    parameter that does not exist.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data", parameters={"ddof": 1, "degrees": 1}))
    assert "degrees" in str(refusal.value)


@pytest.mark.unit
def test_the_recipe_refuses_a_missing_parameter_the_operator_requires() -> None:
    """A parameter the operator requires may not be left out.

    ``stdev`` takes the degrees of freedom as a required argument, because
    an absent choice is not a choice. A recipe that left it out would be
    asking for a statistic whose population nobody named.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data", parameters={}))
    assert "ddof" in str(refusal.value)


@pytest.mark.unit
def test_the_recipe_refuses_a_selection_among_the_parameters() -> None:
    """The selection is a field of its own, and may not also be a parameter.

    A recipe carrying it twice has two selections, and only one of them is
    the one the operator ran -- which is a figure whose numbers came from
    somewhere nobody wrote down.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data", parameters={"ddof": 1, "selection": {"columns": ["value"]}}))
    assert "selection" in str(refusal.value)


@pytest.mark.unit
@pytest.mark.parametrize("axis", ["x", "y"])
def test_the_recipe_refuses_a_column_the_selection_does_not_have(axis: str) -> None:
    """An axis naming a column the selection has not got is refused.

    A column with no data behind it is a column the author invented, and a
    figure that drew one would be showing an axis that is not in the data.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(encoding=_part("encoding", **{axis: "measured"}))
    assert "measured" in str(refusal.value)
    assert "group" in str(refusal.value)


@pytest.mark.unit
def test_a_histogram_may_name_a_count_the_selection_does_not_have() -> None:
    """A histogram's y is the count the renderer derives.

    Every other mark plots two columns of the selection, and a histogram
    counts one column rather than plotting a second, so its y is the name
    the renderer gives the count. The one exception is declared rather than
    written into the check, so it is a fact about the marks and not a
    special case in the code.
    """
    assert Mark.HISTOGRAM in DERIVED_COUNT_MARKS
    recipe = _recipe(encoding=_part("encoding", mark="histogram", y="count"))
    assert recipe.encoding.y == "count"
    assert recipe.encoding.x == "group"


@pytest.mark.unit
def test_the_recipe_refuses_a_selection_with_no_columns() -> None:
    """A selection over no columns is a statistic over nothing."""
    with pytest.raises(RecipeRefusedError):
        _recipe(data=_part("data.selection", columns=[]))


@pytest.mark.unit
def test_the_recipe_refuses_a_selection_that_repeats_a_column() -> None:
    """One column twice is one column, and its cells would be counted twice."""
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data.selection", columns=["value", "value"]))
    assert "value" in str(refusal.value)


@pytest.mark.unit
def test_the_recipe_refuses_a_row_spec_that_is_not_written_as_it_is_stored() -> None:
    """A row boundary written as a word is a malformed row boundary.

    Pydantic would read ``"2"`` as the number 2 and say nothing about it.
    A recipe is written by hand, so a number written as a word is a likely
    mistake, and a recipe quietly rewritten would be hashed in a form its
    author never wrote.
    """
    with pytest.raises(RecipeRefusedError) as refusal:
        _recipe(data=_part("data.selection", rows={"start": "2", "end": "11"}))
    assert "start" in str(refusal.value)


@pytest.mark.unit
def test_the_recipe_refuses_an_unknown_mark() -> None:
    """A mark outside the closed set is refused.

    Not approximated by the nearest mark in the set: a figure drawn as
    something other than what was asked for is a figure nobody checked.
    """
    with pytest.raises(ValidationError) as error:
        _recipe(encoding=_part("encoding", mark="pie"))
    assert "pie" in str(error.value)


@pytest.mark.unit
def test_the_recipe_refuses_an_unknown_output_format() -> None:
    """A format outside the closed set is refused."""
    with pytest.raises(ValidationError) as error:
        _recipe(output=_part("output", format="pdf"))
    assert "pdf" in str(error.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "part",
    ["", "data", "data.selection", "encoding", "output"],
)
def test_the_recipe_refuses_an_unknown_key(part: str) -> None:
    """A key the recipe does not declare is refused.

    This is the test that says "there is no code-execution surface": a
    ``script``, an ``expression`` or a ``module`` would be an unknown key,
    and an unknown key is an error rather than a field nobody reads.
    """
    document = _with_extra_key(part)
    with pytest.raises(ValidationError) as error:
        ChartRecipe.model_validate(document)
    assert "script" in str(error.value)


@pytest.mark.unit
def test_the_recipe_refuses_a_caption_that_says_nothing() -> None:
    """The caption is required, and it may not be empty.

    A figure that does not say what it shows has not said what it is, and
    the caption is the one piece of the figure that states a fact about the
    data rather than a claim about it.
    """
    with pytest.raises(ValidationError):
        _recipe(encoding=_part("encoding", caption=""))
    document = copy.deepcopy(BASE)
    del document["encoding"]["caption"]
    with pytest.raises(ValidationError):
        ChartRecipe.model_validate(document)


@pytest.mark.unit
def test_the_recipe_refuses_an_interpretation_that_says_nothing() -> None:
    """An interpretation may be absent, but an empty one is not an absence.

    "Present but empty" is a third thing, and a recipe that carried it
    would ask the renderer to mark a claim that says nothing.
    """
    with pytest.raises(ValidationError):
        _recipe(encoding=_part("encoding", interpretation=""))


@pytest.mark.unit
def test_a_recipe_with_no_interpretation_carries_none() -> None:
    """A caption that says what is plotted is not an interpretation.

    So a recipe with no interpretation carries no marker, and the renderer
    is the one that adds a marker when there is an interpretation to mark.
    The recipe says only which of the two it has.
    """
    recipe = _recipe()
    assert recipe.encoding.interpretation is None


@pytest.mark.unit
def test_the_caption_and_the_interpretation_are_different_fields() -> None:
    """The two are separate, and neither is derived from the other.

    A caption says what is plotted; an interpretation says what it means.
    Putting them in one field would have put the decision to mark the text
    in the author's hands, and ADR-0004 A10 does not want it there.
    """
    recipe = _recipe(encoding=_part("encoding", interpretation="Group B is heavier than group A."))
    assert recipe.encoding.caption == BASE["encoding"]["caption"]
    assert recipe.encoding.interpretation == "Group B is heavier than group A."

    without = _recipe()
    assert without.encoding.interpretation is None
    assert without.encoding.caption == recipe.encoding.caption


@pytest.mark.unit
def test_the_recipe_refuses_a_dpi_that_is_not_a_positive_number() -> None:
    """A dpi of zero, or of a fraction, is refused.

    A dpi is a decision somebody made, and a default would be a decision
    nobody made.
    """
    with pytest.raises(ValidationError):
        _recipe(output=_part("output", dpi=0))
    with pytest.raises(ValidationError):
        _recipe(output=_part("output", dpi=-1))


@pytest.mark.unit
def test_the_recipe_refuses_a_dpi_written_as_a_string() -> None:
    """A number written as a string is not silently read as a number.

    The project's own rule about numbers that must not be silently
    converted, and it matters here more than anywhere else, because a
    recipe is written by hand.
    """
    with pytest.raises(ValidationError):
        _recipe(output=_part("output", dpi="200"))


@pytest.mark.unit
def test_the_recipe_refuses_a_dpi_beyond_the_bound() -> None:
    """A dpi beyond the bound is refused rather than drawn.

    The bound is a resource limit: a figure at four figures per inch
    allocates a bitmap large enough to exhaust memory before it produced
    anything anybody could open.
    """
    assert MAX_DPI == 600
    with pytest.raises(ValidationError):
        _recipe(output=_part("output", dpi=MAX_DPI + 1))
    assert _recipe(output=_part("output", dpi=MAX_DPI)).output.dpi == MAX_DPI


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    ["/etc/passwd", "../outside.csv", "runs\\exp1.csv", "C:/runs/exp1.csv", "runs/./exp1.csv"],
)
def test_the_recipe_refuses_a_source_outside_the_workspace(source: str) -> None:
    """A recipe may only name a file inside the workspace.

    An absolute path, a path that climbs out, a path with a backslash in it
    and a path with a drive letter are all refused rather than resolved, for
    the reason the workspace's own paths are: a path recorded on one
    platform has to resolve on another, and a path that escapes the
    workspace is a read of something the workspace does not hold.
    """
    with pytest.raises(ValidationError) as error:
        _recipe(data=_part("data.selection", source=source))
    # The refusal has to be about *this* path: a test that only saw "some
    # error" would pass even if the path check had stopped working and
    # something else had started failing.
    assert repr(source) in str(error.value)


@pytest.mark.unit
def test_the_recipe_refuses_a_parameter_that_is_not_a_finite_number() -> None:
    """A parameter of infinity or NaN is refused.

    JSON has no literal for either, so allowing them here would produce
    bytes another reader cannot round-trip -- a silent corruption at the
    boundary, and the boundary is where the recipe's hash is taken.
    """
    with pytest.raises(ValidationError):
        _recipe(data=_part("data", parameters={"ddof": 1, "scale": float("inf")}))
    with pytest.raises(ValidationError):
        _recipe(data=_part("data", parameters={"ddof": 1, "scale": float("nan")}))


@pytest.mark.unit
def test_the_recipe_names_columns_the_corpus_fixture_actually_has() -> None:
    """The recipe under test is built over the corpus's own columns.

    The corpus is the oracle for the data, so the fixture's headers and the
    corpus's statement about them are checked first, and the recipe is
    built over exactly those columns. The column it refuses is one the
    fixture does not have.
    """
    table = read_table_csv((CORPUS_DIR / "basic.csv").read_bytes())
    expected = load_expected("basic.csv")
    assert list(table.headers) == expected["columns"]

    recipe = _recipe(data=_part("data.selection", columns=list(table.headers)))
    assert recipe.data.selection.columns == tuple(table.headers)

    with pytest.raises(RecipeRefusedError):
        _recipe(
            data=_part("data.selection", columns=list(table.headers)),
            encoding=_part("encoding", x="measured"),
        )


@pytest.mark.unit
def test_the_data_recipe_becomes_the_selection_the_operator_runs() -> None:
    """The recipe's selection is the selection the operator is given.

    The recipe names a file; the run path resolves that file to a source
    and its content hash; and this is where the two halves meet. The
    columns, the rows and the policy are the recipe's, unchanged.
    """
    recipe = _recipe()
    selection = recipe.data.selection.to_selection("runs/exp1.csv", "a" * 64)
    assert selection.source_id == "runs/exp1.csv"
    assert selection.content_sha256 == "a" * 64
    assert selection.columns == ("group", "value")
    assert selection.missing is MissingPolicy.EXCLUDE


@pytest.mark.unit
def test_the_data_recipe_refuses_to_bind_a_selection_to_a_malformed_hash() -> None:
    """A selection bound to a malformed hash is a selection bound to nothing."""
    with pytest.raises(ValidationError):
        _recipe().data.selection.to_selection("runs/exp1.csv", "not-a-hash")
