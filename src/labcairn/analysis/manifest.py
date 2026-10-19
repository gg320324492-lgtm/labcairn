"""The manifest: the record that makes a computed number repeatable.

LC-P1-10 computes numbers, and a computed number is a different kind of claim
from a read one. A number read out of a cell is a statement about that cell,
and the ledger checks it -- C3 re-reads the cell and compares. A number
computed from many cells is a statement about a **derivation**, and what makes
it checkable is not a check but this document: the input file's hash, the
selection, the operator and its version, the parameters, the recipe, and the
output's hash.

Three decisions shape the document, and each of them costs something.

**The manifest is the document; the receipt is the record that points at it.**
:mod:`labcairn.reports.receipt` already reserves ``ArtifactKind.MANIFEST``
and ``ArtifactProducerKind.ANALYSIS_OPERATOR`` for this, and the ``artifacts``
table already mirrors the receipt field for field. So there is **no new table
and no migration**: this module produces an :class:`ArtifactReceipt` whose
``relative_path`` names a file, and the file is the manifest.

**One hash lineage, checked rather than asserted.** ADR-0004's re-evaluation
trigger 3 asked that the manifest and the evidence record share a single hash
lineage, and noted that the alignment "may change ``source_content_hash``'s
definition". It does not have to, and here it does not: the manifest's input
hash, the selection's ``content_sha256``, the source's ``content_sha256`` and
the file's actual bytes are **the same value**, and the builder refuses to
produce a manifest in which they are not. The definition of that value --
SHA-256 of the file's raw bytes, lowercase hex -- already has two
implementations in this repository, and this module reuses one of them
(:func:`labcairn.security.approval.content_hash`) rather than adding a third.

**Determinism is scoped to one recorded environment.** The same inputs, the
same parameters and the same environment must produce byte-identical manifest
bytes. That is a testable property, and it is why the manifest records an
environment fingerprint: without it, "identical inputs" is undefined, and the
output hash would be a number whose meaning depends on a machine nobody
recorded. Across environments the claim is semantic only -- the same marks and
the same values, not the same bytes -- and the manifest says so rather than
implying a portability it does not have.

The recipe is the work order's "script", recorded **by path and hash**. It is
a fact about a file rather than a copy of it: a manifest that carried the
recipe's text would be a second copy of a document with its own staleness.
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Final, Self, cast

from pydantic import BaseModel, JsonValue, ValidationError, model_validator

from labcairn.analysis.operators import OperatorIdError, parse_operator_reference
from labcairn.analysis.selection import RowFilter, RowRange, RowSet, Selection
from labcairn.core.schema import LabCairnModel
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.security.approval import content_hash
from labcairn.sources.locators import ComputationLocator
from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    WorkspaceRelativePath,
    require_workspace_relative,
)
from labcairn.sources.source import Source
from labcairn.workspace.outputs import TaskOutputArea
from labcairn.workspace.roots import Workspace

__all__ = [
    "UNSET_HASH_SALT",
    "FileRef",
    "ManifestRefusedError",
    "RenderEnvironment",
    "ReproducibilityManifest",
    "build_figure_receipt",
    "build_manifest",
    "canonical_digest",
    "canonical_json",
    "current_environment",
    "input_drift",
    "manifest_bytes",
    "read_recipe",
    "selection_payload",
    "write_manifest",
]

#: The key the selection occupies inside the locator's parameters.
#:
#: Named, because a selection is not just another parameter: it is *which
#: cells* the other parameters are applied to, and a manifest that recorded it
#: as an anonymous key would lose that.
SELECTION_KEY: Final[str] = "selection"

#: What the fingerprint records when matplotlib has no ``svg.hashsalt`` set.
#:
#: Not a sentinel for a value -- a statement that there is none. Left unset,
#: matplotlib generates a **fresh random salt per render**, so two renders in
#: one environment would not agree byte for byte, and a manifest that said
#: "salt: none" without saying what that means would read like a value.
UNSET_HASH_SALT: Final[str] = "<unset>"


class ManifestRefusedError(RuntimeError):
    """The manifest could not be built, and saying why is the whole answer.

    A refusal rather than a manifest with a blank in it. The alternatives are
    worse: a manifest that recorded no input hash would claim a derivation
    over bytes nobody can name, and one that recorded a *stale* hash without
    saying so would be a false statement about the file rather than an
    absence. The project's rule is that an unknown is never a zero and a
    missing thing is never a blank -- here it is a refusal.
    """


def canonical_json(payload: JsonValue) -> str:
    """Canonical JSON for a JSON-native payload.

    These are the rules :meth:`labcairn.core.schema.LabCairnModel.json_canonical`
    applies to a model -- sorted keys, no incidental whitespace,
    ``ensure_ascii=False`` -- and they are the *same* rules rather than a
    second convention, which the test suite asserts byte for byte. A payload
    is what an operator's result is once it has been read out of Python, and
    a digest over it has to be comparable between two runs on two platforms.

    ``allow_nan=False`` is stricter than ``json_canonical`` can be, because a
    model cannot hold a non-finite float at all -- ``LabCairnModel`` sets
    ``allow_inf_nan=False`` -- whereas a payload arrives from a caller's
    model and might. ``NaN`` is not JSON, so a digest over it would be a
    number no compliant reader could reproduce.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_digest(payload: JsonValue) -> str:
    """The digest of a payload's canonical JSON.

    The algorithm the Skill's ledger already names, ``sha256/canonical-json/v1``
    (``labcairn.skills.ledger.DIGEST_ALGORITHM``): lowercase-hex SHA-256 over
    the canonical bytes. This is the digest of a *document*, not of a file's
    bytes -- the file's bytes are hashed by
    :func:`labcairn.security.approval.content_hash`, which is the one
    implementation of that definition and is not re-implemented here.
    """
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class FileRef(LabCairnModel):
    """One file a derivation depended on, named by where it is and what it holds.

    A fact about a file rather than a copy of it. The bytes are in the
    workspace; the manifest says *which* bytes, and the hash is what makes
    the statement checkable later.
    """

    relative_path: WorkspaceRelativePath
    content_sha256: ContentHash


class RenderEnvironment(LabCairnModel):
    """The environment a derivation ran in, in enough detail to scope a claim.

    The four facts that decide whether a render is byte-reproducible, and
    nothing else. The salt is the one that is easy to miss: left unset,
    matplotlib generates a fresh random salt per render, so two renders in
    one environment differ and the "same inputs, same bytes" claim is false
    for a reason no manifest recorded. :func:`current_environment` reads all
    four from the live process.
    """

    #: The matplotlib that would draw the figure.
    matplotlib_version: NonEmptyText
    #: The salt matplotlib uses for SVG element ids, or :data:`UNSET_HASH_SALT`
    #: when there is none.
    svg_hashsalt: NonEmptyText
    #: The font families a render may use, sorted and without repeats.
    font_families: tuple[NonEmptyText, ...]
    #: The platform the render happened on.
    platform: NonEmptyText

    @model_validator(mode="after")
    def _families_are_canonical(self) -> Self:
        if not self.font_families:
            raise ValueError(
                "the environment records no font family. A render with no font "
                "policy is a render whose bytes depend on whichever font the "
                "machine happened to resolve, and that is an input nobody put "
                "in the manifest."
            )
        if list(self.font_families) != sorted(self.font_families):
            raise ValueError(
                f"the font families are not in sorted order: {list(self.font_families)}. "
                "Sort on write rather than normalising on read -- an environment "
                "that renders two ways cannot be compared."
            )
        if len(set(self.font_families)) != len(self.font_families):
            raise ValueError(
                f"the font families repeat: {list(self.font_families)}. One family "
                "twice is one family, and listing it twice makes the count "
                "answerable two ways."
            )
        return self


class ReproducibilityManifest(LabCairnModel):
    """Everything a reader needs to re-run a derivation and get the same number.

    The six fields the work order names are here, and each is in the place
    the task breakdown puts it:

    * **input file hash** -- :attr:`input_file`'s ``content_sha256``, which is also
      the locator's single input hash;
    * **selection** -- ``locator.parameters["selection"]``;
    * **operator version** -- ``locator.operator_version``, and :attr:`operator`
      for the one spelling a reader will quote;
    * **parameters** -- the rest of ``locator.parameters``;
    * **script/recipe** -- :attr:`recipe`, by path and hash;
    * **output hash** -- :attr:`output_sha256`, the digest of :attr:`output`'s
      canonical JSON.

    The four cross-checks in the validator are the point of the model rather
    than decoration: a manifest whose operator reference disagrees with its
    locator, whose input hash is not the locator's input, whose locator names
    no selection, or whose output hash is not the digest of its output, is
    refused on construction. A document that could hold a contradiction is a
    document nobody can rely on.
    """

    #: The file the derivation read, and the hash of the bytes it read.
    input_file: FileRef
    #: The operator that ran, in the one spelling: ``labcairn.analysis.mean@1.0.0``.
    operator: NonEmptyText
    #: The derived number as this project already writes it.
    locator: ComputationLocator
    #: The recipe the derivation followed, by path and hash.
    recipe: FileRef
    #: The operator's output, as JSON.
    output: JsonValue
    #: The digest of :attr:`output`'s canonical JSON.
    output_sha256: ContentHash
    #: Where the derivation ran.
    environment: RenderEnvironment

    @model_validator(mode="after")
    def _the_views_agree(self) -> Self:
        identifier, version = parse_operator_reference(self.operator)
        if (identifier, version) != (self.locator.operator_id, self.locator.operator_version):
            raise ValueError(
                f"the manifest names the operator {self.operator!r}, which is "
                f"{identifier!r} at version {version!r}, but its locator names "
                f"{self.locator.operator_id!r} at version "
                f"{self.locator.operator_version!r}. One operator, one spelling: "
                "two names for the same run are two manifests that do not "
                "compare equal."
            )
        if self.locator.input_hashes != (self.input_file.content_sha256,):
            raise ValueError(
                f"the manifest's input hash is {self.input_file.content_sha256!r} but its "
                f"locator derives over {list(self.locator.input_hashes)}. The input "
                "file's hash and the derivation's inputs are one value, and a "
                "manifest in which they differ describes a derivation over bytes "
                "it does not name."
            )
        if SELECTION_KEY not in self.locator.parameters:
            raise ValueError(
                f"the locator's parameters carry no {SELECTION_KEY!r}. Which cells "
                "the other parameters apply to is part of what a derivation is, and "
                "a manifest that does not say it describes a computation over "
                "nothing in particular."
            )
        if canonical_digest(self.output) != self.output_sha256:
            raise ValueError(
                f"the manifest records the output hash {self.output_sha256!r}, but "
                f"its output hashes to {canonical_digest(self.output)!r}. The output "
                "hash is the output's; one that is not would be a number about "
                "something else."
            )
        return self


def selection_payload(selection: Selection) -> dict[str, JsonValue]:
    """A selection as canonical JSON.

    Written out by hand rather than dumped by a serialiser, because a
    selection's rows are a **closed union** of three shapes and a serialiser
    that guessed between them would be guessing. The ``kind`` tag is what
    makes the three shapes tell themselves apart, and it is checked by the
    test suite: two of them producing the same JSON would be two selections
    that compare equal.
    """
    return {
        "source_id": selection.source_id,
        "content_sha256": selection.content_sha256,
        "columns": list(selection.columns),
        "rows": _rows_payload(selection.rows),
        "missing": selection.missing.value,
    }


def _rows_payload(rows: RowRange | RowSet | RowFilter) -> dict[str, JsonValue]:
    match rows:
        case RowRange(start=start, end=end):
            return {"kind": "range", "start": start, "end": end}
        case RowSet(rows=members):
            return {"kind": "set", "rows": list(members)}
        case RowFilter(column=column, op=op, value=value):
            return {"kind": "filter", "column": column, "op": op.value, "value": value}


def current_environment() -> RenderEnvironment:
    """The environment this process would render in, as a fingerprint.

    matplotlib is imported **lazily**, for the reason the dependency decision
    records: the text, Markdown, CSV and XLSX paths must not pay for it. A
    manifest built by a scalar operator does not need a renderer either, and
    the fingerprint is recorded all the same -- it says where the run happened,
    and a run that produced a figure has to be scoped to it.
    """
    import matplotlib

    salt = matplotlib.rcParams["svg.hashsalt"]
    families = tuple(sorted(str(family) for family in matplotlib.rcParams["font.family"]))
    return RenderEnvironment(
        matplotlib_version=matplotlib.__version__,
        svg_hashsalt=UNSET_HASH_SALT if salt is None else str(salt),
        font_families=families,
        platform=platform.platform(),
    )


def read_recipe(root: Path, relative_path: str) -> FileRef:
    """The recipe at *relative_path* under *root*, by path and hash.

    The path is checked against the project's own workspace-relative rule
    before the file is opened, so a relative path cannot walk out of the
    root, and the hash comes from the shared content-hash implementation --
    the same function the ledger's own hashes came from.

    This function is not the authorisation boundary. The caller has already
    resolved the path through the workspace, which is what decides whether a
    location may be read at all; what happens here is that the manifest's
    recipe and the bytes that were hashed are **the same file by
    construction**, rather than two things a caller supplied separately and
    could get out of step.

    :raises ManifestRefusedError: when the path is not workspace-relative, or
        the recipe is not there to be read.
    """
    try:
        checked = require_workspace_relative(relative_path)
    except ValueError as error:
        raise ManifestRefusedError(
            f"the recipe path {relative_path!r} is not workspace-relative: {error}"
        ) from error
    target = root / checked
    try:
        digest = content_hash(target)
    except OSError as error:
        raise ManifestRefusedError(
            f"the recipe {checked!r} could not be read: {error}. A manifest that "
            "names a recipe nobody can read is a manifest that records an "
            "unreproducible derivation."
        ) from error
    return FileRef(relative_path=checked, content_sha256=digest)


def build_manifest(
    *,
    source: Source,
    input_path: Path,
    selection: Selection,
    operator: str,
    parameters: Mapping[str, JsonValue],
    recipe: FileRef,
    result: BaseModel,
    environment: RenderEnvironment,
) -> ReproducibilityManifest:
    """The manifest for one derivation.

    :param source: the ingested source the numbers came from. Its
        ``content_sha256`` is the hash of the bytes the analysis read.
    :param input_path: the file those bytes are in, on disk.
    :param selection: which cells were used.
    :param operator: the operator that ran, in the one spelling --
        ``labcairn.analysis.mean@1.0.0``.
    :param parameters: the operator's parameters, **besides** the selection,
        which the builder adds.
    :param recipe: the recipe, by path and hash.
    :param result: the operator's output.
    :param environment: where the derivation ran.
    :raises ManifestRefusedError: when the file's bytes are not the bytes the
        source was ingested from, when the selection is bound to a different
        source, or when the operator reference is not well formed.
    """
    identifier, version = _operator_parts(operator)
    input_sha256 = _input_hash(source, input_path)
    _check_selection_binds_the_source(selection, source)
    _check_parameters_do_not_shadow_the_selection(parameters)

    locator_parameters: dict[str, JsonValue] = {SELECTION_KEY: selection_payload(selection)}
    locator_parameters.update(parameters)

    output = _output_payload(result)
    try:
        return ReproducibilityManifest(
            input_file=FileRef(relative_path=source.relative_path, content_sha256=input_sha256),
            operator=operator,
            locator=ComputationLocator(
                operator_id=identifier,
                operator_version=version,
                parameters=locator_parameters,
                input_hashes=(input_sha256,),
            ),
            recipe=recipe,
            output=output,
            output_sha256=canonical_digest(output),
            environment=environment,
        )
    except ValidationError as error:
        raise ManifestRefusedError(
            f"the manifest could not be built from these facts: {error}. A "
            "manifest that contradicts itself is not a manifest with a blank in "
            "it -- it is a document whose parts disagree, and a reader would have "
            "no way to tell which part to believe."
        ) from error


def _operator_parts(operator: str) -> tuple[str, str]:
    """The id and version an operator reference names.

    The reference is **not** rebuilt here. It is parsed, so that the manifest
    and the receipt quote the same string the catalogue produced, and a
    reference with no version in it is refused rather than recorded as one.
    """
    try:
        return parse_operator_reference(operator)
    except OperatorIdError as error:
        raise ManifestRefusedError(
            f"the operator reference {operator!r} is not well formed: {error}. A "
            "manifest that names no operator version names no code that ran, and "
            "the version is the fact that says which code it was."
        ) from error


def _input_hash(source: Source, input_path: Path) -> str:
    """The hash of the input file, checked against the source's own.

    Two implementations of "the hash of a file's bytes" already exist in this
    repository, and this is one of them -- not a third. The hash is then
    compared with the one the source was ingested under, because a manifest
    that named bytes the ledger has not seen would be a derivation over
    material nobody analysed, and a manifest that named the *old* bytes while
    the file now holds different ones would be a false statement about the
    file.
    """
    try:
        observed = content_hash(input_path)
    except OSError as error:
        raise ManifestRefusedError(
            f"the input file {input_path} could not be read: {error}. The manifest "
            "names the hash of a file, and a file that cannot be read has no hash "
            "to name."
        ) from error
    if observed != source.content_sha256:
        raise ManifestRefusedError(
            f"the input file {input_path} hashes to {observed}, but the source "
            f"{source.source_id!r} was ingested from bytes that hash to "
            f"{source.content_sha256}. The numbers were computed over the ingested "
            "representation, so a manifest built now would describe a derivation "
            "over bytes the analysis never read."
        )
    return observed


def _check_selection_binds_the_source(selection: Selection, source: Source) -> None:
    if selection.source_id != source.source_id:
        raise ManifestRefusedError(
            f"the selection names the source {selection.source_id!r}, but the "
            f"manifest is for {source.source_id!r}. A selection over one file and "
            "a manifest over another are two derivations, and recording one as "
            "the other is the kind of mistake no later reader could see."
        )
    if selection.content_sha256 != source.content_sha256:
        raise ManifestRefusedError(
            f"the selection is bound to bytes that hash to "
            f"{selection.content_sha256}, but the source {source.source_id!r} was "
            f"ingested from bytes that hash to {source.content_sha256}. The "
            "selection and the source are one value, and the manifest refuses to "
            "record two."
        )


def _check_parameters_do_not_shadow_the_selection(parameters: Mapping[str, JsonValue]) -> None:
    if SELECTION_KEY in parameters:
        raise ManifestRefusedError(
            f"the parameters carry a {SELECTION_KEY!r} key, which is where the "
            "builder puts the selection. Two spellings of the selection in one "
            "manifest are two selections, and which one ran would be a matter of "
            "which was read last."
        )


def _output_payload(result: BaseModel) -> JsonValue:
    """The operator's output, as JSON.

    ``mode="json"`` rather than ``model_dump_json()`` because the two differ
    on a non-finite float: the JSON form writes ``null``, which would turn an
    unknown into a value without saying so. The Python-in-JSON form keeps the
    ``NaN``, and the manifest's own validation refuses it -- which is the
    outcome ADR-0004 A8 asks for.
    """
    payload = result.model_dump(mode="json")
    try:
        canonical_json(payload)
    except (TypeError, ValueError) as error:
        raise ManifestRefusedError(
            f"the operator's output is not JSON: {error}. A manifest that "
            "recorded it could not be compared with another run's."
        ) from error
    return cast(JsonValue, payload)


def manifest_bytes(manifest: ReproducibilityManifest) -> bytes:
    """The manifest's bytes -- exactly what is written and exactly what is hashed.

    Canonical, by the project's own convention
    (:meth:`labcairn.core.schema.LabCairnModel.json_canonical`): sorted keys,
    no incidental whitespace, ``ensure_ascii=False``. Two runs over the same
    inputs therefore produce the same bytes, which is what lets a receipt be
    **compared** rather than eyeballed.
    """
    return manifest.json_canonical().encode("utf-8")


def write_manifest(
    workspace: Workspace,
    *,
    key: str,
    manifest: ReproducibilityManifest,
    receipt_id: str,
    created_at: datetime,
    revision: int = 1,
) -> ArtifactReceipt:
    """Write the manifest and return the receipt that records it.

    The file goes through :class:`labcairn.workspace.outputs.TaskOutputArea`,
    which is the only thing in this codebase that writes a file: atomic,
    output-root-only, and it reports what it did. An analysis that opened its
    own file would bypass all of that. The receipt's ``content_sha256`` is the
    writer's own hash of the bytes on disk, so the receipt and the file cannot
    disagree.

    The path in the receipt is derived from where the file actually landed, not
    from a second spelling the caller supplied.
    """
    outputs = TaskOutputArea(workspace)
    write = outputs.write(key, manifest_bytes(manifest))
    relative_path = write.absolute_path.relative_to(workspace.selected_root).as_posix()
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id=str(workspace.task_id),
        kind=ArtifactKind.MANIFEST,
        relative_path=relative_path,
        content_sha256=write.content_hash,
        size_bytes=write.size_bytes,
        revision=revision,
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id=manifest.operator,
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.MATERIAL_FILE,
                target_id=manifest.input_file.relative_path,
                content_sha256=manifest.input_file.content_sha256,
            ),
        ),
        media_type="application/json",
        created_at=created_at,
    )


def build_figure_receipt(
    *,
    manifest_receipt: ArtifactReceipt,
    relative_path: str,
    content_sha256: str,
    size_bytes: int,
    receipt_id: str,
    created_at: datetime,
    revision: int = 1,
    staleness: ArtifactStaleness = ArtifactStaleness.CURRENT,
    staleness_reason: str | None = None,
) -> ArtifactReceipt:
    """The receipt for a figure, whose chain runs back through the manifest.

    The figure is derived from the manifest **and** from everything the
    manifest was derived from, so the chain is linear: file, result, manifest,
    figure. Each link names the one before it, and nothing names a document
    that has not been written.
    """
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id=manifest_receipt.task_id,
        kind=ArtifactKind.FIGURE,
        relative_path=relative_path,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        revision=revision,
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id=manifest_receipt.producer_id,
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.ARTIFACT,
                target_id=manifest_receipt.receipt_id,
                content_sha256=manifest_receipt.content_sha256,
            ),
            *manifest_receipt.derived_from,
        ),
        staleness=staleness,
        staleness_reason=staleness_reason,
        media_type="image/svg+xml",
        created_at=created_at,
    )


def input_drift(manifest: ReproducibilityManifest, input_path: Path) -> str | None:
    """Why the input no longer matches the manifest, or ``None`` when it does.

    The manifest was built over particular bytes. When the file changes, the
    derivation is stale, and ADR-0004 I4 requires that to be **marked** with a
    reason a reader can act on. The reason is returned rather than the
    staleness itself, because the receipt's own model is what pairs a
    ``STALE`` mark with a reason.
    """
    try:
        observed = content_hash(input_path)
    except OSError as error:
        return (
            f"the input file {input_path} can no longer be read: {error}, so the "
            "derivation cannot be checked against it"
        )
    if observed == manifest.input_file.content_sha256:
        return None
    return (
        f"the input file {input_path} now hashes to {observed}, and the manifest "
        f"was built over bytes that hash to {manifest.input_file.content_sha256}"
    )
