"""The manifest: the record that makes a computed number repeatable.

LC-P1-10 T08. The manifest is the artefact that turns "the figure says 5.5"
into "the figure says 5.5, and here is everything that had to be true for
that to be the number". Three properties carry the weight, and each of them
is tested here as a property that could be broken:

**One hash lineage.** The manifest's input hash, the selection's
``content_sha256``, the source's ``content_sha256`` and the file's actual
bytes are one value. That value has two implementations in this repository
already; this module reuses one of them, and the test suite checks that it
did not add a third. A second definition of "the hash of a file" is the kind
of thing that never shows up as a failure -- it shows up as two records of
the same file that do not compare equal, and nobody notices until somebody
compares them.

**Determinism, scoped to one recorded environment.** The same inputs, the
same parameters and the same environment produce byte-identical manifest
bytes. That is only a testable claim because the environment is recorded:
without it, "identical inputs" is undefined and the output hash is a number
whose meaning depends on a machine nobody wrote down.

**Refusal rather than degradation.** A missing hash, a missing operator
version, a recipe that is not there, or an input file whose bytes have
changed since it was ingested are all **refusals**. A manifest with a blank
in it is worse than no manifest, because a blank reads as a fact.

The mutation notes at the end of this file record the ways each property
could be undone and the named test that catches each one. A property no
mutation reached is a property nothing observes.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError

from labcairn.analysis.manifest import (
    UNSET_HASH_SALT,
    FileRef,
    ManifestRefusedError,
    RenderEnvironment,
    ReproducibilityManifest,
    build_figure_receipt,
    build_manifest,
    canonical_digest,
    canonical_json,
    current_environment,
    input_drift,
    manifest_bytes,
    read_recipe,
    selection_payload,
    write_manifest,
)
from labcairn.analysis.operators import OperatorArgs
from labcairn.analysis.selection import (
    FilterOp,
    MissingPolicy,
    RowFilter,
    RowRange,
    RowSet,
    Selection,
)
from labcairn.core.ids import TaskId, new_id
from labcairn.core.schema import LabCairnModel
from labcairn.material.ingest import ingest_bytes
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationTargetKind,
)
from labcairn.security.approval import content_hash
from labcairn.sources.locators import ComputationLocator, LocatorKind
from labcairn.sources.source import Source
from labcairn.workspace.roots import Workspace

#: The material the manifest is built over. Small, and its statistics are
#: known, though what the manifest records is the *file*, not the statistics.
MATERIAL: bytes = b"value,group\n1,A\n2,B\n3,A\n4,B\n5,A\n"

#: A second material, so that a test can change the input without changing
#: anything else about the derivation.
OTHER_MATERIAL: bytes = b"value,group\n1,A\n2,B\n3,A\n4,B\n5,A\n6,B\n"

#: A fixed moment. The manifest itself carries no timestamp -- that is what
#: lets two builds of the same derivation agree byte for byte -- but the
#: receipts do.
NOW: datetime = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

#: The reference the manifest quotes. Spelled the one way the operator
#: contract spells it.
OPERATOR: str = "labcairn.analysis.mean@1.0.0"

#: A body distinctive enough to look for in a manifest that should not have
#: copied the recipe.
RECIPE_BODY: bytes = b'{"marker": "SECRET-RECIPE-BODY"}'


class _Args(OperatorArgs):
    """An argument model, so the operator contract's own object can be built."""

    column: str


class _Result(BaseModel):
    """A result shaped like an operator's: closed, frozen, and plain.

    Plain rather than a :class:`~labcairn.core.schema.LabCairnModel`, because
    the operators' own result models are plain, and a manifest that only
    worked for one of the two shapes would be a manifest the catalogue
    could not use.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float | None
    n_used: int
    unit: str | None = None


class _Wrapper(LabCairnModel):
    """A model whose canonical JSON is the project's convention, wrapped.

    Used to compare :func:`canonical_json` against
    :meth:`labcairn.core.schema.LabCairnModel.json_canonical` byte for byte.
    """

    payload: JsonValue


def _environment(**overrides: Any) -> RenderEnvironment:
    """A fixed environment, so a test that changes one thing changes one thing."""
    fields: dict[str, Any] = {
        "matplotlib_version": "3.11.2",
        "svg_hashsalt": "labcairn",
        "font_families": ("sans-serif",),
        "platform": "TestOS-1.0",
    }
    fields.update(overrides)
    return RenderEnvironment(**fields)


def _catalogue_reference() -> str:
    """The reference the operator contract produces for a real operator.

    Built through :func:`labcairn.analysis.operators.operator_reference` so
    that the string the manifest quotes is the string the contract produces,
    rather than a second spelling written out in a test.
    """
    from labcairn.analysis.operators import Operator, operator_reference

    operator = Operator(
        operator_id="labcairn.analysis.mean",
        operator_version="1.0.0",
        args_model=_Args,
        result_model=_Result,
        accepted_locator_kinds=frozenset({LocatorKind.CSV}),
        summary="the arithmetic mean of a numeric column",
    )
    return operator_reference(operator)


def _ingest(tmp_path: Path, data: bytes, name: str = "exp1.csv") -> tuple[Source, Path]:
    """Ingest *data* and put the same bytes on disk, as the source row and the file.

    The two are the same bytes on purpose: the manifest's whole claim is that
    the hash it writes is the hash of the file the analysis read.
    """
    material = ingest_bytes(
        data,
        relative_path=f"runs/{name}",
        display_name=name,
        ingested_at=NOW,
    )
    path = tmp_path / "runs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return material.source, path


def _selection(source: Source) -> Selection:
    return Selection(
        source_id=source.source_id,
        content_sha256=source.content_sha256,
        columns=("value",),
        rows=RowRange(2, 6),
        missing=MissingPolicy.EXCLUDE,
    )


def _recipe(tmp_path: Path, name: str = "recipe.json", body: bytes = RECIPE_BODY) -> FileRef:
    path = tmp_path / name
    path.write_bytes(body)
    return read_recipe(tmp_path, name)


def _manifest(tmp_path: Path, **overrides: Any) -> ReproducibilityManifest:
    """A manifest over the standard material, with whatever the test changes."""
    source, path = _ingest(tmp_path, MATERIAL)
    fields: dict[str, Any] = {
        "source": source,
        "input_path": path,
        "selection": _selection(source),
        "operator": OPERATOR,
        "parameters": {},
        "recipe": _recipe(tmp_path),
        "result": _Result(value=3.0, n_used=5),
        "environment": _environment(),
    }
    fields.update(overrides)
    return build_manifest(**fields)


def _recorded_selection(manifest: ReproducibilityManifest) -> dict[str, JsonValue]:
    """The selection as the manifest recorded it, as a mapping."""
    recorded = manifest.locator.parameters["selection"]
    assert isinstance(recorded, dict)
    return recorded


def _rows_record(selection: Selection) -> dict[str, JsonValue]:
    """The row specification as the manifest would record it, as a mapping."""
    recorded = selection_payload(selection)["rows"]
    assert isinstance(recorded, dict)
    return recorded


def _workspace(tmp_path: Path) -> Workspace:
    return Workspace.bind(tmp_path, task_id=TaskId(new_id()))


# --------------------------------------------------------------------------- #
# The six fields
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_manifest_carries_the_six_fields_the_work_order_names(tmp_path: Path) -> None:
    """Input hash, selection, operator version, parameters, recipe, output hash.

    Each of them is checked *where* it lives, not merely that something like
    it exists: the work order's fields have one home each, and a manifest
    that put the selection somewhere else would be a manifest two readers
    could disagree about.
    """
    source, path = _ingest(tmp_path, MATERIAL)
    manifest = _manifest(tmp_path)

    assert manifest.input_file.content_sha256 == content_hash(path)
    assert _recorded_selection(manifest) == selection_payload(_selection(source))
    assert manifest.locator.operator_version == "1.0.0"
    assert manifest.locator.operator_id == "labcairn.analysis.mean"
    assert manifest.recipe.relative_path == "recipe.json"
    assert manifest.recipe.content_sha256 == content_hash(tmp_path / "recipe.json")
    assert manifest.output_sha256 == canonical_digest(manifest.output)


@pytest.mark.unit
def test_the_operator_is_quoted_the_one_way_the_contract_spells_it(tmp_path: Path) -> None:
    """The manifest's operator string is the contract's own reference.

    Two spellings of one operator would be two manifests that do not compare
    equal, and the disagreement would not crash -- it would be two records of
    the same run that simply differ.
    """
    manifest = _manifest(tmp_path)
    assert manifest.operator == _catalogue_reference()
    assert manifest.operator == OPERATOR


@pytest.mark.unit
def test_the_recipe_is_recorded_by_path_and_hash(tmp_path: Path) -> None:
    """The recipe is a fact about a file, not a copy of it.

    A manifest that carried the recipe's text would be a second copy of a
    document, with its own staleness: the file could change and the manifest
    would still claim the old recipe.
    """
    manifest = _manifest(tmp_path)
    assert manifest.recipe.relative_path == "recipe.json"
    assert manifest.recipe.content_sha256 == content_hash(tmp_path / "recipe.json")
    assert b"SECRET-RECIPE-BODY" not in manifest_bytes(manifest)


# --------------------------------------------------------------------------- #
# One hash lineage
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_input_hash_is_the_sources_own_content_hash(tmp_path: Path) -> None:
    """One value, four views: the file, the source, the selection, the locator.

    The comparison against the file's bytes is the part that is not
    vacuous: it is computed by the shared implementation, so a manifest that
    used any other definition of "the hash of a file" would fail here.
    """
    source, path = _ingest(tmp_path, MATERIAL)
    manifest = _manifest(tmp_path)

    assert manifest.input_file.content_sha256 == source.content_sha256
    assert manifest.input_file.content_sha256 == content_hash(path)
    assert manifest.locator.input_hashes == (source.content_sha256,)
    assert _recorded_selection(manifest)["content_sha256"] == source.content_sha256


@pytest.mark.unit
def test_the_manifest_adds_no_third_hash_implementation() -> None:
    """The module reuses the project's content-hash function rather than writing one.

    Checked on the source, because the failure this guards against is not a
    wrong answer but a second definition of the right question: two
    implementations of "the hash of a file's bytes" agree until the day one
    of them changes, and then two records of one file stop comparing equal.
    """
    import labcairn.analysis.manifest as module

    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = {
        (node.module, alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ("labcairn.security.approval", "content_hash") in imported, (
        "the manifest does not import the shared content-hash implementation"
    )

    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "content_hash" not in defined, "the manifest defines its own content hash"

    digests = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sha256"
    ]
    assert digests, "the module computes no digest at all"
    for call in digests:
        assert call.args and all(
            isinstance(argument, ast.Call)
            and isinstance(argument.func, ast.Attribute)
            and argument.func.attr == "encode"
            for argument in call.args
        ), "a digest in the manifest is taken over something other than text"


@pytest.mark.unit
def test_a_file_whose_bytes_changed_is_a_refusal(tmp_path: Path) -> None:
    """The manifest describes bytes the analysis read, and refuses other bytes.

    Building one here would describe a derivation over material the numbers
    were not computed from, and the description would be indistinguishable
    from a true one.
    """
    source, path = _ingest(tmp_path, MATERIAL)
    path.write_bytes(MATERIAL + b"6,B\n")

    with pytest.raises(ManifestRefusedError) as caught:
        build_manifest(
            source=source,
            input_path=path,
            selection=_selection(source),
            operator=OPERATOR,
            parameters={},
            recipe=_recipe(tmp_path),
            result=_Result(value=3.0, n_used=5),
            environment=_environment(),
        )
    assert source.content_sha256 in str(caught.value)


@pytest.mark.unit
def test_a_missing_input_file_is_a_refusal(tmp_path: Path) -> None:
    """A file that cannot be read has no hash to name."""
    source, path = _ingest(tmp_path, MATERIAL)
    path.unlink()

    with pytest.raises(ManifestRefusedError):
        build_manifest(
            source=source,
            input_path=path,
            selection=_selection(source),
            operator=OPERATOR,
            parameters={},
            recipe=_recipe(tmp_path),
            result=_Result(value=3.0, n_used=5),
            environment=_environment(),
        )


@pytest.mark.unit
def test_a_selection_bound_to_different_bytes_is_a_refusal(tmp_path: Path) -> None:
    """The selection and the source are one value, and the manifest says so."""
    source, path = _ingest(tmp_path, MATERIAL)
    other = Selection(
        source_id=source.source_id,
        content_sha256="b" * 64,
        columns=("value",),
        rows=RowRange(2, 6),
        missing=MissingPolicy.EXCLUDE,
    )

    with pytest.raises(ManifestRefusedError) as caught:
        build_manifest(
            source=source,
            input_path=path,
            selection=other,
            operator=OPERATOR,
            parameters={},
            recipe=_recipe(tmp_path),
            result=_Result(value=3.0, n_used=5),
            environment=_environment(),
        )
    assert "b" * 64 in str(caught.value)


@pytest.mark.unit
def test_a_selection_over_another_source_is_a_refusal(tmp_path: Path) -> None:
    """A selection over one file and a manifest over another are two derivations."""
    source, path = _ingest(tmp_path, MATERIAL)
    other = Selection(
        source_id="src-somewhere-else",
        content_sha256=source.content_sha256,
        columns=("value",),
        rows=RowRange(2, 6),
        missing=MissingPolicy.EXCLUDE,
    )

    with pytest.raises(ManifestRefusedError):
        build_manifest(
            source=source,
            input_path=path,
            selection=other,
            operator=OPERATOR,
            parameters={},
            recipe=_recipe(tmp_path),
            result=_Result(value=3.0, n_used=5),
            environment=_environment(),
        )


@pytest.mark.unit
def test_parameters_that_shadow_the_selection_are_a_refusal(tmp_path: Path) -> None:
    """Two spellings of the selection in one manifest are two selections."""
    source, path = _ingest(tmp_path, MATERIAL)
    with pytest.raises(ManifestRefusedError):
        build_manifest(
            source=source,
            input_path=path,
            selection=_selection(source),
            operator=OPERATOR,
            parameters={"selection": {"kind": "range"}},
            recipe=_recipe(tmp_path),
            result=_Result(value=3.0, n_used=5),
            environment=_environment(),
        )


# --------------------------------------------------------------------------- #
# The recipe
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_a_recipe_that_is_not_there_is_a_refusal(tmp_path: Path) -> None:
    """A manifest naming a recipe nobody can read records an unreproducible run."""
    with pytest.raises(ManifestRefusedError) as caught:
        read_recipe(tmp_path, "absent.json")
    assert "absent.json" in str(caught.value)


@pytest.mark.unit
def test_a_recipe_path_that_escapes_the_root_is_a_refusal(tmp_path: Path) -> None:
    """The workspace-relative rule is the project's own, and it is applied."""
    outside = tmp_path.parent / "outside.json"
    outside.write_bytes(b"{}")

    with pytest.raises(ManifestRefusedError):
        read_recipe(tmp_path, "../outside.json")
    with pytest.raises(ManifestRefusedError):
        read_recipe(tmp_path, str(outside))


@pytest.mark.unit
def test_the_recipe_is_the_file_that_was_hashed(tmp_path: Path) -> None:
    """The recorded path and the hashed bytes are one file by construction.

    A builder that took a path and a hash separately would let them drift,
    and this is the test that would catch it: a recipe whose *contents*
    changed must change the recorded hash.
    """
    recipe = _recipe(tmp_path)
    assert recipe.content_sha256 == content_hash(tmp_path / "recipe.json")

    (tmp_path / "recipe.json").write_bytes(b'{"marker": "OTHER"}')
    changed = read_recipe(tmp_path, "recipe.json")
    assert changed.content_sha256 != recipe.content_sha256
    assert changed.relative_path == recipe.relative_path


# --------------------------------------------------------------------------- #
# The operator reference
# --------------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    "reference",
    [
        "labcairn.analysis.mean",
        "labcairn.analysis.mean@",
        "labcairn.analysis.mean@1.0",
        "mean@1.0.0",
        "labcairn.other.mean@1.0.0",
    ],
)
def test_an_operator_reference_that_names_no_version_is_a_refusal(
    tmp_path: Path, reference: str
) -> None:
    """A manifest with no operator version names no code that ran.

    The version is the fact that says *which* code ran, and a reference with
    no version in it is not a reference at all.
    """
    with pytest.raises(ManifestRefusedError):
        _manifest(tmp_path, operator=reference)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_same_inputs_produce_byte_identical_manifest_bytes(tmp_path: Path) -> None:
    """The property the manifest exists to support.

    Two builds of the same derivation over the same material, with the same
    parameters and the same environment, must produce the same bytes -- so
    that a receipt can be **compared** rather than eyeballed.
    """
    first = manifest_bytes(_manifest(tmp_path))
    second = manifest_bytes(_manifest(tmp_path))
    assert first == second


@pytest.mark.unit
def test_changing_the_input_changes_the_manifest_bytes(tmp_path: Path) -> None:
    """A different file is a different derivation, and the manifest says so."""
    other_source, other_path = _ingest(tmp_path, OTHER_MATERIAL, name="exp2.csv")

    first = _manifest(tmp_path)
    second = _manifest(
        tmp_path,
        source=other_source,
        input_path=other_path,
        selection=_selection(other_source),
    )

    assert first.input_file.content_sha256 != second.input_file.content_sha256
    assert manifest_bytes(first) != manifest_bytes(second)


@pytest.mark.unit
def test_changing_the_operator_version_changes_the_manifest_bytes(tmp_path: Path) -> None:
    """A version bump is a code change, and the manifest has to show it."""
    first = manifest_bytes(_manifest(tmp_path))
    second = manifest_bytes(_manifest(tmp_path, operator="labcairn.analysis.mean@1.0.1"))
    assert first != second


@pytest.mark.unit
def test_changing_the_environment_changes_the_manifest_bytes(tmp_path: Path) -> None:
    """Without the environment recorded, "identical inputs" is undefined."""
    first = manifest_bytes(_manifest(tmp_path))
    second = manifest_bytes(_manifest(tmp_path, environment=_environment(platform="OtherOS-2.0")))
    assert first != second


@pytest.mark.unit
def test_changing_the_parameters_changes_the_manifest_bytes(tmp_path: Path) -> None:
    """Parameters are part of the derivation, not decoration on it."""
    first = manifest_bytes(_manifest(tmp_path))
    second = manifest_bytes(_manifest(tmp_path, parameters={"ddof": 1}))
    assert first != second


@pytest.mark.unit
def test_changing_the_selection_changes_the_manifest_bytes(tmp_path: Path) -> None:
    """Which cells were used is part of what the number means."""
    source, _ = _ingest(tmp_path, MATERIAL)
    other = Selection(
        source_id=source.source_id,
        content_sha256=source.content_sha256,
        columns=("value",),
        rows=RowRange(2, 5),
        missing=MissingPolicy.EXCLUDE,
    )
    first = manifest_bytes(_manifest(tmp_path))
    second = manifest_bytes(_manifest(tmp_path, selection=other))
    assert first != second


@pytest.mark.unit
def test_changing_the_recipe_changes_the_manifest_bytes(tmp_path: Path) -> None:
    """A different recipe is a different derivation."""
    first = manifest_bytes(_manifest(tmp_path))
    second = manifest_bytes(_manifest(tmp_path, recipe=_recipe(tmp_path, body=b'{"b": 2}')))
    assert first != second


# --------------------------------------------------------------------------- #
# Canonical bytes
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_manifest_bytes_are_canonical(tmp_path: Path) -> None:
    """Sorted keys, no incidental whitespace, and no escaping of what need not be escaped.

    The last part is not cosmetic: ``ensure_ascii=False`` is what keeps a
    non-ASCII value readable in the manifest, and a manifest that escaped it
    would still be canonical by some other convention and would not be the
    manifest this project hashes.
    """
    manifest = _manifest(tmp_path, result=_Result(value=3.0, n_used=5, unit="µg"))
    raw = manifest_bytes(manifest)

    assert b"\\u" not in raw
    assert "µg" in raw.decode("utf-8")

    parsed = json.loads(raw)
    assert list(parsed) == sorted(parsed)
    assert b", " not in raw and b": " not in raw


@pytest.mark.unit
def test_the_manifest_uses_the_projects_canonical_json_convention() -> None:
    """One convention, not two.

    ``LabCairnModel.json_canonical`` and :func:`canonical_json` are compared
    byte for byte on the same payload. If they ever disagree, one of them is
    wrong and a digest computed by the other would not match.
    """
    payload: JsonValue = {"b": 1, "a": ["x", {"z": "ü", "y": None}], "c": 1.5}
    expected = '{"payload":' + canonical_json(payload) + ',"schema_version":1}'
    assert _Wrapper(payload=payload).json_canonical() == expected


@pytest.mark.unit
def test_the_output_hash_is_the_digest_of_the_output_in_canonical_json(tmp_path: Path) -> None:
    """The output hash is about the output.

    Written out here rather than reusing the module's own helper, so that the
    test does not agree with the code by construction.
    """
    manifest = _manifest(tmp_path)
    expected = hashlib.sha256(
        json.dumps(
            manifest.output,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert manifest.output_sha256 == expected


@pytest.mark.unit
def test_a_manifest_whose_output_hash_disagrees_with_its_output_is_refused(
    tmp_path: Path,
) -> None:
    """The model checks its own consistency on construction.

    A document that could hold a contradiction is a document nobody can rely
    on, and the check is cheaper here than at the point of comparison.
    """
    manifest = _manifest(tmp_path)
    with pytest.raises(ValidationError):
        ReproducibilityManifest(
            input_file=manifest.input_file,
            operator=manifest.operator,
            locator=manifest.locator,
            recipe=manifest.recipe,
            output=manifest.output,
            output_sha256="c" * 64,
            environment=manifest.environment,
        )


@pytest.mark.unit
def test_a_manifest_whose_operator_disagrees_with_its_locator_is_refused(
    tmp_path: Path,
) -> None:
    """One operator, one spelling."""
    manifest = _manifest(tmp_path)
    with pytest.raises(ValidationError):
        ReproducibilityManifest(
            input_file=manifest.input_file,
            operator="labcairn.analysis.mean@2.0.0",
            locator=manifest.locator,
            recipe=manifest.recipe,
            output=manifest.output,
            output_sha256=manifest.output_sha256,
            environment=manifest.environment,
        )


@pytest.mark.unit
def test_a_manifest_whose_input_is_not_its_locators_is_refused(tmp_path: Path) -> None:
    """The input hash and the derivation's inputs are one value."""
    manifest = _manifest(tmp_path)
    with pytest.raises(ValidationError):
        ReproducibilityManifest(
            input_file=FileRef(
                relative_path=manifest.input_file.relative_path,
                content_sha256="d" * 64,
            ),
            operator=manifest.operator,
            locator=manifest.locator,
            recipe=manifest.recipe,
            output=manifest.output,
            output_sha256=manifest.output_sha256,
            environment=manifest.environment,
        )


@pytest.mark.unit
def test_a_manifest_without_a_selection_is_refused(tmp_path: Path) -> None:
    """Which cells the parameters apply to is part of what a derivation is."""
    manifest = _manifest(tmp_path)
    parameters = {
        key: value for key, value in manifest.locator.parameters.items() if key != "selection"
    }
    locator = ComputationLocator(
        operator_id=manifest.locator.operator_id,
        operator_version=manifest.locator.operator_version,
        parameters=parameters,
        input_hashes=manifest.locator.input_hashes,
    )
    with pytest.raises(ValidationError):
        ReproducibilityManifest(
            input_file=manifest.input_file,
            operator=manifest.operator,
            locator=locator,
            recipe=manifest.recipe,
            output=manifest.output,
            output_sha256=manifest.output_sha256,
            environment=manifest.environment,
        )


@pytest.mark.unit
def test_an_output_that_is_not_a_number_is_refused(tmp_path: Path) -> None:
    """``NaN`` is not JSON, and a digest over it no compliant reader could reproduce."""
    source, path = _ingest(tmp_path, MATERIAL)
    with pytest.raises(ManifestRefusedError):
        build_manifest(
            source=source,
            input_path=path,
            selection=_selection(source),
            operator=OPERATOR,
            parameters={},
            recipe=_recipe(tmp_path),
            result=_Result(value=float("nan"), n_used=5),
            environment=_environment(),
        )


# --------------------------------------------------------------------------- #
# The environment fingerprint
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_environment_fingerprint_names_the_four_facts() -> None:
    """The matplotlib version, the salt, the font policy and the platform.

    Asserted as a *field set* rather than as four values, so that dropping
    one of them is a failure rather than a shorter fingerprint.
    """
    assert set(RenderEnvironment.model_fields) - {"schema_version"} == {
        "matplotlib_version",
        "svg_hashsalt",
        "font_families",
        "platform",
    }

    environment = current_environment()
    import matplotlib

    assert environment.matplotlib_version == matplotlib.__version__
    salt = matplotlib.rcParams["svg.hashsalt"]
    assert environment.svg_hashsalt == (UNSET_HASH_SALT if salt is None else str(salt))
    assert environment.font_families == tuple(
        sorted(str(family) for family in matplotlib.rcParams["font.family"])
    )
    assert environment.platform


@pytest.mark.unit
def test_the_environment_fingerprint_reports_the_salt_matplotlib_has(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fingerprint says what matplotlib has, not what the machine happens to have.

    Left unset, matplotlib generates a fresh random salt per render, so two
    renders in one environment do not agree byte for byte. A fingerprint that
    reported "no salt" on a machine that has one would be hiding the very
    fact it exists to record, so the salt is read from the live settings and
    the *unset* case is named rather than left blank.
    """
    import matplotlib

    monkeypatch.setitem(matplotlib.rcParams, "svg.hashsalt", "test-salt")
    assert current_environment().svg_hashsalt == "test-salt"

    monkeypatch.setitem(matplotlib.rcParams, "svg.hashsalt", None)
    assert current_environment().svg_hashsalt == UNSET_HASH_SALT


@pytest.mark.unit
def test_the_environment_fingerprint_is_the_same_twice_in_one_environment() -> None:
    """A fingerprint that changed between two calls would change the manifest."""
    assert current_environment() == current_environment()


@pytest.mark.unit
def test_an_environment_with_no_font_family_is_refused() -> None:
    """A render with no font policy is a render whose bytes depend on the machine."""
    with pytest.raises(ValidationError):
        _environment(font_families=())


# --------------------------------------------------------------------------- #
# The selection payload
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_selection_payload_names_every_field_of_the_selection(tmp_path: Path) -> None:
    """The payload cannot fall behind the selection it describes.

    A field added to ``Selection`` and not to the payload would be a field
    the manifest recorded nothing about, and the manifest would still look
    complete.
    """
    source, _ = _ingest(tmp_path, MATERIAL)
    payload = selection_payload(_selection(source))
    assert set(payload) == {field.name for field in dataclasses.fields(Selection)}


@pytest.mark.unit
def test_the_three_row_specs_serialise_to_three_different_shapes(tmp_path: Path) -> None:
    """Two of them producing the same JSON would be two selections that compare equal."""
    source, _ = _ingest(tmp_path, MATERIAL)
    payloads = []
    for rows in (
        RowRange(2, 6),
        RowSet((2, 3, 4)),
        RowFilter("value", FilterOp.GT, "0"),
    ):
        selection = Selection(
            source_id=source.source_id,
            content_sha256=source.content_sha256,
            columns=("value",),
            rows=rows,
            missing=MissingPolicy.EXCLUDE,
        )
        payloads.append(_rows_record(selection))

    kinds = {payload["kind"] for payload in payloads}
    assert kinds == {"range", "set", "filter"}
    assert len({json.dumps(payload, sort_keys=True) for payload in payloads}) == 3


# --------------------------------------------------------------------------- #
# The receipts
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_the_manifest_receipt_names_the_material_file_with_its_hash(tmp_path: Path) -> None:
    """The chain link LC-P1-06 walks when a source changes.

    ``MATERIAL_FILE`` is one of the two target kinds that must carry a hash:
    a chain link with no hash is a link nothing can invalidate.
    """
    workspace = _workspace(tmp_path)
    manifest = _manifest(tmp_path)
    receipt = write_manifest(
        workspace,
        key="manifest.json",
        manifest=manifest,
        receipt_id="receipt-1",
        created_at=NOW,
    )

    assert receipt.kind is ArtifactKind.MANIFEST
    assert receipt.produced_by is ArtifactProducerKind.ANALYSIS_OPERATOR
    assert receipt.producer_id == manifest.operator
    assert len(receipt.derived_from) == 1
    reference = receipt.derived_from[0]
    assert reference.target_kind is DerivationTargetKind.MATERIAL_FILE
    assert reference.target_id == manifest.input_file.relative_path
    assert reference.content_sha256 == manifest.input_file.content_sha256


@pytest.mark.unit
def test_the_figure_receipt_names_the_manifest_with_its_hash(tmp_path: Path) -> None:
    """The chain is linear: file, result, manifest, figure.

    Each link names the one before it, and nothing names a document that has
    not been written.
    """
    workspace = _workspace(tmp_path)
    manifest = _manifest(tmp_path)
    manifest_receipt = write_manifest(
        workspace,
        key="manifest.json",
        manifest=manifest,
        receipt_id="receipt-1",
        created_at=NOW,
    )
    figure = build_figure_receipt(
        manifest_receipt=manifest_receipt,
        relative_path="output/figure.svg",
        content_sha256="e" * 64,
        size_bytes=1234,
        receipt_id="receipt-2",
        created_at=NOW,
    )

    assert figure.kind is ArtifactKind.FIGURE
    assert figure.producer_id == manifest.operator
    assert figure.derived_from[0].target_kind is DerivationTargetKind.ARTIFACT
    assert figure.derived_from[0].target_id == manifest_receipt.receipt_id
    assert figure.derived_from[0].content_sha256 == manifest_receipt.content_sha256
    assert figure.derived_from[1].target_kind is DerivationTargetKind.MATERIAL_FILE
    assert figure.derived_from[1].content_sha256 == manifest.input_file.content_sha256


@pytest.mark.unit
def test_the_manifest_is_written_through_the_workspace_writer(tmp_path: Path) -> None:
    """The file is where the receipt says it is, and holds the canonical bytes.

    The receipt's hash is the writer's own hash of the bytes on disk, so the
    receipt and the file cannot disagree -- and the path in the receipt is
    derived from where the file landed rather than from a second spelling
    the caller supplied.
    """
    workspace = _workspace(tmp_path)
    manifest = _manifest(tmp_path)
    receipt = write_manifest(
        workspace,
        key="manifest.json",
        manifest=manifest,
        receipt_id="receipt-1",
        created_at=NOW,
    )

    written = workspace.selected_root / receipt.relative_path
    assert written.is_file()
    assert written.read_bytes() == manifest_bytes(manifest)
    assert receipt.content_sha256 == content_hash(written)
    assert receipt.size_bytes == written.stat().st_size
    assert receipt.relative_path.startswith("output/")


@pytest.mark.unit
def test_a_stale_figure_names_the_reason_it_is_stale(tmp_path: Path) -> None:
    """ADR-0004 I4: a stale mark nobody can act on is decoration.

    The reason is the receipt's own pairing rule, so the manifest module
    cannot mark a figure stale without saying why.
    """
    workspace = _workspace(tmp_path)
    manifest = _manifest(tmp_path)
    manifest_receipt = write_manifest(
        workspace,
        key="manifest.json",
        manifest=manifest,
        receipt_id="receipt-1",
        created_at=NOW,
    )
    reason = input_drift(manifest, tmp_path / "runs" / "exp1.csv")
    assert reason is None

    (tmp_path / "runs" / "exp1.csv").write_bytes(MATERIAL + b"6,B\n")
    reason = input_drift(manifest, tmp_path / "runs" / "exp1.csv")
    assert reason is not None
    assert manifest.input_file.content_sha256 in reason

    figure = build_figure_receipt(
        manifest_receipt=manifest_receipt,
        relative_path="output/figure.svg",
        content_sha256="e" * 64,
        size_bytes=1234,
        receipt_id="receipt-2",
        created_at=NOW,
        staleness=ArtifactStaleness.STALE,
        staleness_reason=reason,
    )
    assert figure.staleness is ArtifactStaleness.STALE
    assert figure.staleness_reason == reason


@pytest.mark.unit
def test_a_receipt_with_a_stale_mark_and_no_reason_is_refused() -> None:
    """The receipt's own rule, and it holds for the manifest's figures too."""
    with pytest.raises(ValidationError):
        ArtifactReceipt(
            receipt_id="receipt-1",
            task_id="task-1",
            kind=ArtifactKind.FIGURE,
            relative_path="output/figure.svg",
            content_sha256="e" * 64,
            size_bytes=1,
            produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
            producer_id=OPERATOR,
            staleness=ArtifactStaleness.STALE,
            created_at=NOW,
        )


# --------------------------------------------------------------------------- #
# Mutation notes
# --------------------------------------------------------------------------- #
#
# Each of these is a way the module's properties could be undone, and the
# named test that catches it. They are recorded here because a property that
# no mutation reached is a property nothing observes. Every one of the twenty
# was applied to the module and run; all twenty were caught.
#
#   1. the input drift check removed
#      -> test_a_file_whose_bytes_changed_is_a_refusal
#   2. the input hash copied from the source without hashing the file
#      -> test_a_file_whose_bytes_changed_is_a_refusal
#   3. a second content-hash implementation
#      -> test_the_manifest_adds_no_third_hash_implementation
#   4. the operator reference validated nowhere
#      -> test_an_operator_reference_that_names_no_version_is_a_refusal
#   5. the environment fingerprint ignored
#      -> test_changing_the_environment_changes_the_manifest_bytes
#   6. the salt reported as unset whatever matplotlib has
#      -> test_the_environment_fingerprint_reports_the_salt_matplotlib_has
#   7. the selection dropped from the locator
#      -> test_a_manifest_without_a_selection_is_refused
#   8. the parameters dropped from the locator
#      -> test_changing_the_parameters_changes_the_manifest_bytes
#   9. the recipe recorded with a made-up hash
#      -> test_the_recipe_is_recorded_by_path_and_hash
#  10. the output hash made a constant
#      -> test_the_output_hash_is_the_digest_of_the_output_in_canonical_json
#  11. the manifest's own consistency not checked
#      -> test_a_manifest_whose_output_hash_disagrees_with_its_output_is_refused
#  12. the manifest written outside the workspace writer
#      -> test_the_manifest_is_written_through_the_workspace_writer
#  13. the figure's chain link to the manifest dropped
#      -> test_the_figure_receipt_names_the_manifest_with_its_hash
#  14. the manifest's chain link to the material file dropped
#      -> test_the_manifest_receipt_names_the_material_file_with_its_hash
#  15. the selection payload's row tag dropped
#      -> test_the_three_row_specs_serialise_to_three_different_shapes
#  16. a non-finite output accepted
#      -> test_an_output_that_is_not_a_number_is_refused
#  17. the manifest's bytes not canonical
#      -> test_the_manifest_bytes_are_canonical
#  18. the canonical JSON convention drifting
#      -> test_the_manifest_uses_the_projects_canonical_json_convention
#  19. the receipt's producer made a constant
#      -> test_the_manifest_receipt_names_the_material_file_with_its_hash
#  20. the written file not exactly the canonical bytes
#      -> test_the_manifest_is_written_through_the_workspace_writer
#
# Two properties are asserted rather than mutated, because a mutation of them
# is not expressible: the operator version and the environment fingerprint
# are *inside* the manifest, so removing either one changes the bytes, and
# that is what the two "changing the ..." tests above measure.
