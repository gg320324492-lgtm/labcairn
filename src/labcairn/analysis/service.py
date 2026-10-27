"""The run path: from a granted ``analysis.run`` to a recorded artefact.

Everything else in :mod:`labcairn.analysis` is a *description*. A selection
says which cells; an operator says what to compute over them; a manifest says
how to repeat the computation. This module is the part that turns a description
into an **effect**, and an effect needs three things a description does not
have: consent, a bound on how much work it may do, and a record that it
happened.

Five decisions shape the path, and each of them costs something.

**The consent is the existing approval machinery, and it is not optional.**
An ``analysis.run`` approval is bound to the capability, the resource key and
the **arguments digest**, so an approval to analyse one selection does not
authorise another -- a different selection is a different digest, and the
digest is recomputed at the moment of use rather than read off the row. The
source binding is checked too: an approval promised a file at a hash, and a
file that has drifted since is a refusal rather than a run over different
bytes. The cost is that a caller must obtain an approval before it may
analyse anything, and that the approval is spent even when the run later
fails; the ADR buys that deliberately, because re-asking a human is cheap and
repeating a side effect is not.

**The source is resolved, not assumed.** A run reads the **ledger's** current
text, not the file: the numbers were computed over the ingested
representation, and a manifest that described a derivation over bytes the
analysis never read would be a false statement. Resolving the source is
therefore three separate facts -- the path, the ledger's row, and the file's
bytes -- and the run refuses when they disagree. The cost is that the caller
has to say which material it means: a selection names a source id and the
hash that source was ingested under, and a run over a material the ledger has
never seen is refused rather than quietly analysed as an empty one. A
spreadsheet with more than one sheet is refused for the same reason: a
selection names a row and a header and no sheet, and an address that cannot be
told apart is not an address anybody chose.

**The bounds are the enforceable ones, and the unenforceable one is named.**
A row limit and a cell-count limit can be checked *before* a single cell is
read, so they are enforced. A wall-clock timeout on an in-process numeric loop
cannot: nothing in this process can interrupt a tight loop in Python, and a
timeout that does not fire is worse than no timeout at all. It is therefore
named in :data:`UNENFORCED_LIMITS` rather than shipped.

**One refusal type, and a reason for each.** Every way this path can say no
raises :class:`AnalysisRefusedError` with an :class:`AnalysisRefusal` reason
and a message that names what is wrong. The refusals raised by the machinery
this path calls -- the selection's, the units', the manifest's -- are
translated rather than swallowed, and the original is kept as the cause.

**A run that produced a number and left no record has produced nothing.** The
manifest is written before the figure, because the figure's chain names the
manifest; the receipts are written last, because a receipt is a record of
something that happened.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final, Protocol, cast

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.analysis.catalog import operator_for
from labcairn.analysis.manifest import (
    ManifestRefusedError,
    ReproducibilityManifest,
    build_figure_receipt,
    build_manifest,
    current_environment,
    read_recipe,
    selection_payload,
    write_manifest,
)
from labcairn.analysis.operators import Operator, RegisteredOperator, operator_reference
from labcairn.analysis.selection import (
    FilterOp,
    MissingPolicy,
    RowFilter,
    RowRange,
    RowSet,
    Selection,
    SelectionRefusedError,
)
from labcairn.analysis.units import UnitDisagreementError
from labcairn.analysis.values import CellAddress, ValueSource, records_blank_cells
from labcairn.core.ids import ApprovalId, new_id
from labcairn.db.materials import current_texts
from labcairn.db.models import SourceRow, SourceTextRow
from labcairn.db.repository import TaskStore
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.security.approval import (
    ApprovalLedger,
    AuthorizationRefusedError,
    NoSuchApprovalError,
    content_hash,
)
from labcairn.security.capabilities import (
    AnalysisRunArgs,
    CapabilityId,
    UnknownArgumentKeyError,
    parse_args,
)
from labcairn.security.paths import CanonicalPath, RootKind
from labcairn.security.policy import Permission, PermissionPolicy, ResourceRef
from labcairn.sources.locators import LocatorKind
from labcairn.sources.primitives import ContentHash, NonEmptyText
from labcairn.sources.source import Source, SourceIdentifier, SourceKind, SourceReadability
from labcairn.workspace.outputs import TaskOutputArea
from labcairn.workspace.roots import Workspace, WorkspaceError

__all__ = [
    "UNENFORCED_LIMITS",
    "AnalysisRefusal",
    "AnalysisRefusedError",
    "AnalysisRequest",
    "AnalysisRun",
    "FigureRenderer",
    "RunLimits",
    "analysis_arguments",
    "run_analysis",
    "selection_from_payload",
]


#: The bounds this build does **not** enforce, named rather than shipped.
#:
#: ``wall_clock_timeout`` is the one ARCHITECTURE.md's "size/row limits and
#: timeouts *where enforceable*" asks for and this build cannot deliver. The
#: reason is not an oversight: a timeout on an in-process numeric loop needs
#: either a separate process to kill or a signal that can interrupt the
#: interpreter, and CPython offers neither portably -- ``SIGALRM`` does not
#: exist on Windows, and a thread cannot preempt the thread holding the GIL.
#: Shipping a timeout that does not fire would be a claim of boundedness that
#: nothing enforces, and a reader would have no way to tell it from one that
#: does.
#:
#: The row and cell limits in :class:`RunLimits` **are** enforceable, because
#: they are checked before a cell is read.
UNENFORCED_LIMITS: Final[frozenset[str]] = frozenset({"wall_clock_timeout"})

#: The content-hash shape, taken from the project's own primitive rather than
#: written out again. ``Selection`` is a plain dataclass, so its hash field is
#: not validated by anything but this check.
_CONTENT_HASH: Final[TypeAdapter[str]] = TypeAdapter(ContentHash)

#: The non-empty-text shape, likewise.
_NON_EMPTY: Final[TypeAdapter[str]] = TypeAdapter(NonEmptyText)

#: A spreadsheet cell reference, split into its column letters and its row.
_CELL_REF: Final[re.Pattern[str]] = re.compile(r"^(?P<letters>[A-Z]{1,3})(?P<row>[1-9][0-9]{0,6})$")


class AnalysisRefusal(StrEnum):
    """Why the run path said no.

    Enumerated so a caller can branch on the reason without reading a message,
    and so that "the run was refused" and "the run was refused *for that
    reason*" are two different facts.
    """

    #: The capability's arguments, or the operator's parameters, are not usable.
    ARGUMENTS_INVALID = "arguments_invalid"
    #: The catalogue holds no operator with that id.
    OPERATOR_NOT_REGISTERED = "operator_not_registered"
    #: The path could not be admitted, or does not name a source root.
    PATH_REFUSED = "path_refused"
    #: The ledger holds no source with that id.
    SOURCE_NOT_FOUND = "source_not_found"
    #: The source is not ``readable``. ADR-0004 A7: unreadable material is
    #: neither analysed nor cited, and an unreadable source is not an empty one.
    SOURCE_UNREADABLE = "source_unreadable"
    #: The file's bytes are not the bytes the source was ingested from.
    SOURCE_DRIFTED = "source_drifted"
    #: The material has more than one sheet, so a row and a header do not
    #: name one address.
    SOURCE_AMBIGUOUS = "source_ambiguous"
    #: The selection is bound to a different source, or to different bytes.
    SELECTION_MISMATCH = "selection_mismatch"
    #: The policy denied the request.
    PERMISSION_DENIED = "permission_denied"
    #: No such approval, or it was never issued.
    APPROVAL_MISSING = "approval_missing"
    #: The approval does not cover this request.
    APPROVAL_REFUSED = "approval_refused"
    #: The run would read more rows or more cells than the bounds allow.
    LIMITS_EXCEEDED = "limits_exceeded"
    #: The operator's **run** was refused, whatever raised it: the selection
    #: could not be resolved, the cells disagree about their units, or a
    #: column's header declares a unit its own cells contradict.
    #:
    #: One member for all three, and the reason is the vocabulary's shape
    #: rather than an accident: a new member would have to be handled by every
    #: consumer of the reason, and it would still not say *which* column
    #: conflicted or why -- the message says that, and the message is
    #: carried verbatim from the exception that raised it.
    OPERATOR_REFUSED = "operator_refused"
    #: The manifest could not be built.
    MANIFEST_REFUSED = "manifest_refused"
    #: The recipe is not there to be read.
    RECIPE_UNREADABLE = "recipe_unreadable"


class AnalysisRefusedError(RuntimeError):
    """The run path refused, and says why.

    One type for every refusal, with a machine-readable reason and a message
    that names what is wrong. The refusals raised by the machinery this path
    calls are translated into this one rather than swallowed, and the original
    is kept as the cause -- so nothing is lost by the translation, and a
    caller has one thing to catch.
    """

    def __init__(self, reason: AnalysisRefusal, detail: str) -> None:
        super().__init__(f"analysis refused ({reason.value}): {detail}")
        self.reason = reason
        self.detail = detail


class FigureRenderer(Protocol):
    """The renderer this path is given.

    T07 builds the implementation and must not import this module, so the
    contract is stated here and the implementation is written against it. Two
    methods, and the order between them is the run path's, not the renderer's.

    ``prepare()`` runs **before** the manifest is built, because the manifest's
    :class:`~labcairn.analysis.manifest.RenderEnvironment` reads the salt, the
    font families and the platform from the live process: the environment has to
    be in its declared state before it is recorded, or the manifest describes a
    render that did not happen.

    ``render()`` returns ``None`` for a result that is not a figure, and that
    is how the path knows there is nothing to write.
    """

    def prepare(self) -> None:
        """Put the render environment into its declared state."""
        ...

    def render(self, operator_id: str, result: BaseModel) -> bytes | None:
        """The figure's bytes, or ``None`` when this result is not a figure."""
        ...


@dataclass(frozen=True, slots=True)
class RunLimits:
    """The bounds a run is held to.

    Both are enforceable in-process, and both are checked **before** a cell is
    read: a limit that is checked after the work has been done is a report,
    not a bound.

    ``max_rows`` bounds the number of rows a selection can name, and
    ``max_cells`` the number of cells a selection can reach. A range that names
    a million rows is bounded by the million, not by the ten the file happens
    to hold, because resolving a range reads an address per row it names.
    """

    #: The most physical rows one run may address.
    max_rows: int = 10_000
    #: The most cells one run may read.
    max_cells: int = 1_000_000

    def __post_init__(self) -> None:
        if self.max_rows < 1:
            raise ValueError(f"max_rows is {self.max_rows}, and a run may not read no rows.")
        if self.max_cells < 1:
            raise ValueError(f"max_cells is {self.max_cells}, and a run may not read no cells.")


@dataclass(frozen=True, slots=True)
class AnalysisRequest:
    """One analysis run, as the caller states it.

    ``root_id`` names the source root the material lives in, and it is named
    rather than inferred because a resource key is *root-relative*: the same
    key under two roots is two different files, and the approval is bound to
    one of them.

    ``arguments`` are the capability's own arguments -- ``path``,
    ``operator_id``, ``recipe`` and ``parameters`` -- and they are validated against
    :class:`~labcairn.security.capabilities.AnalysisRunArgs`, whose model is
    closed. An unrecognised key is a typo or a newer caller, and both deserve
    to be loud.
    """

    approval_id: ApprovalId
    root_id: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    """What one run produced.

    The result is the operator's own object, the manifest is the record that
    makes it repeatable, and the receipts are the records that it happened.
    ``figure_receipt`` is ``None`` when the operator's result was not a
    figure, which is the renderer's own word for it and not this path's guess.
    """

    source: Source
    selection: Selection
    result: BaseModel
    manifest: ReproducibilityManifest
    manifest_receipt: ArtifactReceipt
    figure_receipt: ArtifactReceipt | None


def selection_from_payload(payload: Mapping[str, JsonValue]) -> Selection:
    """The selection a canonical payload names.

    The inverse of :func:`labcairn.analysis.manifest.selection_payload`, and
    deliberately its **only** inverse: the payload the manifest writes is the
    payload this reads, so a selection has exactly one JSON spelling. A second
    one would be a second thing for a reader to disagree about, and the
    manifest's docstring is explicit that the row specification is a closed
    union of three shapes that must not be guessed between -- which is why the
    ``kind`` tag is read here rather than inferred.

    :raises AnalysisRefusedError: when the payload is not a selection.
    """
    missing = _required(payload, "missing")
    if not isinstance(missing, str):
        raise _bad_payload(f"the selection's 'missing' is {type(missing).__name__}, not text.")
    try:
        policy = MissingPolicy(missing)
    except ValueError as error:
        raise _bad_payload(
            f"the selection's missing-value policy is {missing!r}, and it is not one of "
            f"{sorted(item.value for item in MissingPolicy)}."
        ) from error

    columns = _required(payload, "columns")
    if not isinstance(columns, list) or not all(isinstance(name, str) for name in columns):
        raise _bad_payload("the selection's 'columns' must be a list of header names.")
    names = tuple(_non_empty(name, "column") for name in columns)

    source_id = _non_empty(_required(payload, "source_id"), "source_id")
    content_sha256 = _hash(_required(payload, "content_sha256"))

    rows_payload = _required(payload, "rows")
    if not isinstance(rows_payload, Mapping):
        raise _bad_payload("the selection's 'rows' must be the row specification object.")
    rows = _rows_from_payload(rows_payload)

    try:
        return Selection(
            source_id=source_id,
            content_sha256=content_sha256,
            columns=names,
            rows=rows,
            missing=policy,
        )
    except ValueError as error:
        raise _bad_payload(f"the selection is not a selection: {error}") from error


def _rows_from_payload(payload: Mapping[str, JsonValue]) -> RowRange | RowSet | RowFilter:
    """The row specification a payload names, read through its ``kind`` tag.

    Dispatched on the tag rather than on the fields, because the three shapes
    are a closed union and a reader that guessed between them would be
    guessing.
    """
    kind = payload.get("kind")
    match kind:
        case "range":
            start = _row_number(payload, "start")
            end = _row_number(payload, "end")
            try:
                return RowRange(start=start, end=end)
            except ValueError as error:
                raise _bad_payload(f"the row range is not a row range: {error}") from error
        case "set":
            members = payload.get("rows")
            if not isinstance(members, list):
                raise _bad_payload("a row set must be a list of row numbers.")
            numbers: list[int] = []
            for item in members:
                if not isinstance(item, int) or isinstance(item, bool):
                    raise _bad_payload("a row set must be a list of row numbers.")
                numbers.append(item)
            try:
                return RowSet(rows=tuple(numbers))
            except ValueError as error:
                raise _bad_payload(f"the row set is not a row set: {error}") from error
        case "filter":
            column = payload.get("column")
            if not isinstance(column, str):
                raise _bad_payload("a row filter must name the column it filters on.")
            op = payload.get("op")
            if not isinstance(op, str):
                raise _bad_payload("a row filter must name the comparison it makes.")
            try:
                comparison = FilterOp(op)
            except ValueError as error:
                raise _bad_payload(
                    f"a row filter's comparison is {op!r}, and it is not one of "
                    f"{sorted(item.value for item in FilterOp)}."
                ) from error
            value = payload.get("value")
            if not isinstance(value, str):
                raise _bad_payload("a row filter must name the value it compares with.")
            try:
                return RowFilter(column=column, op=comparison, value=value)
            except ValueError as error:
                raise _bad_payload(f"the row filter is not a row filter: {error}") from error
        case _:
            raise _bad_payload(
                f"the row specification's 'kind' is {kind!r}, and it is not one of "
                "'range', 'set' or 'filter'."
            )


def analysis_arguments(arguments: Mapping[str, Any]) -> dict[str, object]:
    """The arguments an ``analysis.run`` is bound to.

    ADR-0003's digest is computed over exactly this mapping, and this function
    is how a caller produces it -- at grant time and, again, at the moment of
    use. Recomputing it is the load-bearing part of the whole consent
    mechanism: a check that trusted the digest stored on the row would be
    satisfied by any row at all.

    The parameters are the **canonical** form of the operator's arguments, so
    two spellings of the same selection produce the same digest, and a
    different selection produces a different one. That is the property the
    work order names: an approval to analyse one selection does not authorise
    another.

    :raises AnalysisRefusedError: when the arguments or the parameters are
        not usable.
    """
    capability_args = _capability_arguments(arguments)
    operator = _operator_for(capability_args.operator_id).operator
    validated = _validated_arguments(operator, capability_args.parameters)
    return {
        "path": capability_args.path,
        "operator_id": capability_args.operator_id,
        "recipe": capability_args.recipe,
        "parameters": _canonical_parameters(operator, validated),
    }


def run_analysis(
    *,
    request: AnalysisRequest,
    store: TaskStore,
    workspace: Workspace,
    policy: PermissionPolicy,
    ledger: ApprovalLedger,
    renderer: FigureRenderer,
    limits: RunLimits | None = None,
    now: datetime | None = None,
) -> AnalysisRun:
    """Run one analysis, from a granted capability to a recorded artefact.

    The order is the one the task breakdown fixes, and it is not incidental.
    One dependency is made explicit rather than hidden: **the selection is
    built before the source is resolved**, because a selection names the
    source it is about -- its id and the hash that source was ingested under
    -- and that binding is what identifies the material in the ledger.

    1. **admit the path** into the named source root, so that a path naming no
       source root is refused before anything else happens;
    2. **build the selection** from the capability's parameters, validated
       against the operator's own argument model;
    3. **resolve the source** -- the ledger's row for the selection's binding,
       the file's bytes, and the source's readability. A source that is not
       ``readable`` is refused, and a file whose bytes have moved since the
       ingest is refused;
    4. **evaluate the operator** from the catalogue, by its id;
    5. **prepare the environment**, then **write the manifest**, which hashes
       the *result* and not the figure;
    6. **render**, if the operator produced a figure, and write it;
    7. **record the receipts**.

    The consent sits between the checks that ask *may this run start* and the
    work itself. Everything before the approval -- the arguments, the
    operator, the path, the source, the policy verdict and the bounds -- is a
    question about whether the run may happen at all, and a refusal there does
    **not** spend the approval: re-asking a human is cheap, and burning
    consent on a request that was never allowed to start is not. The approval
    is consumed before the operator runs, because the operator's evaluation
    *is* the operation the capability names, and an approval that could be
    spent on two evaluations could be spent on two runs.

    :raises AnalysisRefusedError: for every refusal this path makes.
    """
    moment = now if now is not None else datetime.now(UTC)
    bounds = limits if limits is not None else RunLimits()

    # -- 1. the path ------------------------------------------------------- #
    capability_args = _capability_arguments(request.arguments)
    canonical = _canonical_path(workspace, request.root_id, capability_args.path)

    # -- 2. the selection, and the operator that will validate it ---------- #
    registered = _operator_for(capability_args.operator_id)
    operator = registered.operator
    validated = _validated_arguments(operator, capability_args.parameters)
    selection = _selection_argument(operator, validated)

    # -- 3. the source ----------------------------------------------------- #
    source = _resolve_source(store.session, selection, canonical)

    # -- the checks that ask whether the run may start --------------------- #
    _check_policy(policy, workspace, canonical)
    cells = _cells_for(store.session, source)
    _check_bounds(bounds, selection, cells)

    # -- the consent ------------------------------------------------------- #
    _consume_approval(
        ledger=ledger,
        policy=policy,
        workspace=workspace,
        request=request,
        canonical=canonical,
        source=source,
        # Derived again here, from the caller's arguments, rather than carried
        # over from the step above: the digest has to be recomputed at the
        # moment of use, not remembered from an earlier derivation of it.
        arguments=analysis_arguments(request.arguments),
        now=moment,
    )

    # -- 4. the operator --------------------------------------------------- #
    result = _evaluate(registered, validated, cells)

    # -- 5. the environment and the manifest ------------------------------- #
    renderer.prepare()
    manifest = _build_manifest(
        source=source,
        canonical=canonical,
        selection=selection,
        operator=operator,
        validated=validated,
        result=result,
        recipe=capability_args.recipe,
        workspace=workspace,
    )
    run_token = new_id().hex
    manifest_receipt = write_manifest(
        workspace,
        key=_manifest_key(operator, run_token),
        manifest=manifest,
        receipt_id=f"manifest-{run_token}",
        created_at=moment,
    )
    figure_receipt = _write_figure(
        workspace=workspace,
        renderer=renderer,
        operator=operator,
        result=result,
        manifest_receipt=manifest_receipt,
        run_token=run_token,
        created_at=moment,
    )

    # -- 6. the figure, and 7. the receipts -------------------------------- #
    receipts = [manifest_receipt]
    if figure_receipt is not None:
        receipts.append(figure_receipt)
    with store.unit(workspace.task_id) as work:
        for receipt in receipts:
            work.put_artifact(receipt)

    return AnalysisRun(
        source=source,
        selection=selection,
        result=result,
        manifest=manifest,
        manifest_receipt=manifest_receipt,
        figure_receipt=figure_receipt,
    )


# --------------------------------------------------------------------------- #
# The steps
# --------------------------------------------------------------------------- #


def _capability_arguments(raw: Mapping[str, Any]) -> AnalysisRunArgs:
    """The capability's arguments, validated against its closed model.

    The closed model is the point: an unrecognised key is a typo or a newer
    caller, and both deserve to be loud rather than ignored.
    """
    try:
        parsed = parse_args(CapabilityId.ANALYSIS_RUN, raw)
    except UnknownArgumentKeyError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            str(error),
        ) from error
    except ValidationError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            f"the analysis.run arguments are not usable: {error}",
        ) from error
    return cast(AnalysisRunArgs, parsed)


def _operator_for(operator_id: str) -> RegisteredOperator[Any, Any]:
    """The operator the catalogue holds under that id, or a refusal.

    The catalogue is built from the operators' own id constants, so an id it
    does not hold names no code that could run -- which is a different failure
    from a mis-spelled id, and one that cannot be recovered by trying again.
    """
    registered = operator_for(operator_id)
    if registered is None:
        raise AnalysisRefusedError(
            AnalysisRefusal.OPERATOR_NOT_REGISTERED,
            f"{operator_id!r} names no operator this build implements. The catalogue is "
            "built from the operators' own id constants, so an id that is not in it "
            "names no code that could run.",
        )
    return registered


def _validated_arguments(operator: Operator[Any, Any], parameters: Mapping[str, Any]) -> BaseModel:
    """The operator's arguments, validated against its own argument model.

    The selection is decoded first, so that the model validates a
    :class:`~labcairn.analysis.selection.Selection` rather than a mapping it
    would have to guess the shape of.
    """
    decoded = _decode_parameters(operator, parameters)
    try:
        return cast(BaseModel, operator.args_model.model_validate(decoded))
    except ValidationError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            f"the parameters are not what {operator.operator_id} takes: {error}",
        ) from error


def _decode_parameters(
    operator: Operator[Any, Any], parameters: Mapping[str, Any]
) -> dict[str, Any]:
    """The parameters, with any selection payload read into a selection.

    The field that holds a selection is found by its **declared type**, not by
    its name, so a rename cannot silently turn a selection into an opaque
    mapping.
    """
    decoded = dict(parameters)
    for name, field in operator.args_model.model_fields.items():
        annotation = field.annotation
        if not (isinstance(annotation, type) and issubclass(annotation, Selection)):
            continue
        payload = decoded.get(name)
        if payload is None:
            continue
        if not isinstance(payload, Mapping):
            raise AnalysisRefusedError(
                AnalysisRefusal.ARGUMENTS_INVALID,
                f"the {name!r} parameter must be the canonical selection payload, and "
                f"{type(payload).__name__} is not one. There is one spelling of a "
                "selection: the one selection_payload writes.",
            )
        decoded[name] = selection_from_payload(cast(Mapping[str, JsonValue], payload))
    return decoded


def _selection_argument(operator: Operator[Any, Any], validated: BaseModel) -> Selection:
    """The selection the operator's arguments name.

    Refused when the operator names none, or names more than one: a run that
    reads no cells is not an analysis, and two selections are two questions
    with no rule saying which one was asked.
    """
    found = [
        getattr(validated, name)
        for name in operator.args_model.model_fields
        if isinstance(getattr(validated, name, None), Selection)
    ]
    if not found:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            f"{operator.operator_id} names no selection, so a run over it would read no "
            "cells. An analysis operator says which cells it is about.",
        )
    if len(found) > 1:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            f"{operator.operator_id} names {len(found)} selections, and nothing says which "
            "one was asked.",
        )
    return cast(Selection, found[0])


def _canonical_parameters(
    operator: Operator[Any, Any], validated: BaseModel
) -> dict[str, JsonValue]:
    """The operator's arguments, in the one JSON form they are digested in.

    A selection is rendered by :func:`labcairn.analysis.manifest.selection_payload`
    rather than by the model serialiser, because the serialiser would drop the
    row specification's ``kind`` tag and two different row shapes could then
    produce the same JSON.
    """
    payload: dict[str, JsonValue] = {}
    for name in operator.args_model.model_fields:
        value = getattr(validated, name)
        if isinstance(value, Selection):
            payload[name] = selection_payload(value)
        else:
            payload[name] = cast(JsonValue, value)
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            f"the parameters of {operator.operator_id} are not JSON: {error}. A digest "
            "over them could not be reproduced by another reader.",
        ) from error
    return payload


def _canonical_path(workspace: Workspace, root_id: str, key: str) -> CanonicalPath:
    """The path, admitted into the named source root.

    The root is named by the caller rather than searched for, because a
    resource key is root-relative: the same key under two roots is two
    different files, and the approval is bound to one of them.
    """
    try:
        root = workspace.root_for(root_id)
    except WorkspaceError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.PATH_REFUSED,
            f"the root {root_id!r} is not bound to this workspace: {error}",
        ) from error
    if root.kind is not RootKind.SOURCE:
        raise AnalysisRefusedError(
            AnalysisRefusal.PATH_REFUSED,
            f"the root {root_id!r} is a {root.kind.value} root, and a run reads supplied "
            "material. A source root is read-only by construction, which is where the "
            "promise that analysis never writes to the material comes from.",
        )
    try:
        return workspace.path_in(key, root_id)
    except WorkspaceError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.PATH_REFUSED,
            f"the path {key!r} was refused in root {root_id!r}: {error}",
        ) from error


def _resolve_source(session: Session, selection: Selection, canonical: CanonicalPath) -> Source:
    """The material the run is about, and the three facts that must agree.

    The **ledger's** row, by the source id the selection names; the file's
    **bytes**, at the path; and the selection's own **binding**. The row's
    readability is checked here, because ADR-0004 A7 excludes unreadable
    material from being analysed, and an unreadable source is not an empty
    one -- it is a source this build could not look at.
    """
    row = session.scalar(select(SourceRow).where(SourceRow.source_id == selection.source_id))
    if row is None:
        raise AnalysisRefusedError(
            AnalysisRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {selection.source_id!r}, so the "
            "selection names a material that was never ingested. A run reads what the "
            "ledger holds, not what the caller remembers.",
        )
    source = _source_from_row(row)
    if source.readability is not SourceReadability.READABLE:
        raise AnalysisRefusedError(
            AnalysisRefusal.SOURCE_UNREADABLE,
            f"the source {source.source_id!r} is {source.readability.value}, not "
            f"readable. ADR-0004 A7 excludes unreadable material from being analysed, "
            f"and it is not an empty source: {source.readability_disclosure or ''}".strip(),
        )
    if selection.content_sha256 != source.content_sha256:
        raise AnalysisRefusedError(
            AnalysisRefusal.SELECTION_MISMATCH,
            f"the selection is bound to bytes that hash to {selection.content_sha256}, "
            f"but the source {source.source_id!r} was ingested from bytes that hash to "
            f"{source.content_sha256}. The selection and the source are one value.",
        )
    try:
        observed = content_hash(canonical.real_path)
    except OSError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.SOURCE_DRIFTED,
            f"the file {canonical.real_path} could not be read: {error}. A file that "
            "cannot be read has no hash to compare.",
        ) from error
    if observed != source.content_sha256:
        raise AnalysisRefusedError(
            AnalysisRefusal.SOURCE_DRIFTED,
            f"the file {canonical.real_path} now hashes to {observed}, but the source "
            f"{source.source_id!r} was ingested from bytes that hash to "
            f"{source.content_sha256}. The numbers would be computed over the "
            "ingested representation, so a run now would be a run over different "
            "bytes than the ones that were analysed.",
        )
    return source


def _source_from_row(row: SourceRow) -> Source:
    """The ledger's row, as the contract's own :class:`Source`.

    Projected rather than kept as a row, because the manifest and the
    selection are written against the contract and the contract is what
    validates the pair.
    """
    try:
        return Source(
            source_id=row.source_id,
            kind=SourceKind(row.kind),
            display_name=row.display_name,
            relative_path=row.relative_path,
            content_sha256=row.content_sha256,
            size_bytes=row.size_bytes,
            readability=SourceReadability(row.readability),
            readability_disclosure=row.readability_disclosure,
            identifiers=tuple(SourceIdentifier.model_validate(item) for item in row.identifiers),
            ingested_at=row.ingested_at,
        )
    except (ValidationError, ValueError) as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.SOURCE_NOT_FOUND,
            f"the ledger's row for {row.source_id!r} is not a source this build can read: {error}",
        ) from error


def _check_policy(policy: PermissionPolicy, workspace: Workspace, canonical: CanonicalPath) -> None:
    """The permission verdict, and a refusal when it is a deny.

    ADR-0003's default-deny order is the policy's own; this only asks the one
    question and reports the answer. An ``ASK`` is not a deny, but it is not an
    allow either, and this path has no way to ask -- so it is refused rather
    than treated as consent.
    """
    decision = policy.evaluate(
        task_id=workspace.task_id,
        capability=CapabilityId.ANALYSIS_RUN.value,
        resource=ResourceRef.from_canonical(canonical),
    )
    if decision.permission is Permission.DENY:
        raise AnalysisRefusedError(
            AnalysisRefusal.PERMISSION_DENIED,
            f"the policy denied analysis.run on {canonical.resolved_key!r}: "
            f"{decision.reason.value}"
            + (f" (rule: {decision.matched_rule})" if decision.matched_rule else ""),
        )
    if decision.permission is not Permission.ALLOW:
        raise AnalysisRefusedError(
            AnalysisRefusal.PERMISSION_DENIED,
            f"the policy asked about analysis.run on {canonical.resolved_key!r} and this "
            "path has no way to ask. An approval is not a policy verdict, and a "
            "question that nobody answered is not consent.",
        )


def _consume_approval(
    *,
    ledger: ApprovalLedger,
    policy: PermissionPolicy,
    workspace: Workspace,
    request: AnalysisRequest,
    canonical: CanonicalPath,
    source: Source,
    arguments: Mapping[str, object],
    now: datetime,
) -> None:
    """The approval, consumed -- or a refusal naming why not.

    The digest is **recomputed** here from the arguments as they are right now
    and compared with the one the approval carries. A check that trusted the
    stored digest would be satisfied by any row at all, since whoever can write
    a row can write its digest. The source's content hash is in the digest's
    ``depends_on``, so an approval for one material does not authorise another.
    """
    try:
        ledger.consume(
            request.approval_id,
            now=now,
            task_id=workspace.task_id,
            capability=CapabilityId.ANALYSIS_RUN.value,
            resource=canonical,
            args=dict(arguments),
            depends_on=(source.content_sha256,),
            current_policy_digest=policy.digest(),
            resolve_source=lambda key: workspace.path_in(key, request.root_id).real_path,
        )
    except NoSuchApprovalError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.APPROVAL_MISSING,
            f"no approval {request.approval_id} was issued, or it has already been "
            "consumed. An analysis without an approval is an analysis nobody agreed to.",
        ) from error
    except AuthorizationRefusedError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.APPROVAL_REFUSED,
            f"the approval does not cover this run: {error.refusal.value}. "
            f"{error.args[0] if error.args else ''}".strip(),
        ) from error


def _cells_for(session: Session, source: Source) -> ValueSource:
    """The material's cells, as the analysis layer reads them.

    Read from the **ledger**, and from its current extraction: the same bytes
    may be held under more than one extraction, and the current one is the
    newest row for each address. That rule is stated once, in
    :func:`labcairn.db.materials.current_texts`, and this path asks the store
    for it rather than working it out here.

    The evidence index keeps **its own** copy of the same ordering, because
    it resolves one address at a time from a raw connection and cannot be
    used in bulk. The two are held in step by a test that asks both readers
    which row is current and requires them to answer alike -- not by the code
    sharing one implementation.
    """
    if source.kind is SourceKind.CSV:
        locator_kind = LocatorKind.CSV
    elif source.kind is SourceKind.XLSX:
        locator_kind = LocatorKind.XLSX
    else:
        raise AnalysisRefusedError(
            AnalysisRefusal.ARGUMENTS_INVALID,
            f"the source {source.source_id!r} is {source.kind.value} material, and the "
            "operators read tables. A PDF has no cells to select.",
        )
    rows = current_texts(session, source_content_sha256=source.content_sha256)
    return _LedgerCells(rows, kind=locator_kind)


def _check_bounds(bounds: RunLimits, selection: Selection, cells: ValueSource) -> None:
    """The limits, checked before a cell is read.

    A limit checked afterwards is a report, not a bound, so the budget is
    computed from the *specification* -- how many addresses the selection can
    name -- rather than from the cells that turned out to hold something.
    """
    rows, cells_read = _budget(selection, cells)
    if rows > bounds.max_rows:
        raise AnalysisRefusedError(
            AnalysisRefusal.LIMITS_EXCEEDED,
            f"the selection names {rows} rows, over the {bounds.max_rows} one run may "
            "address. The bound is on the addresses the selection names, not on the "
            "cells that happen to hold something.",
        )
    if cells_read > bounds.max_cells:
        raise AnalysisRefusedError(
            AnalysisRefusal.LIMITS_EXCEEDED,
            f"the selection can reach {cells_read} cells, over the {bounds.max_cells} one "
            "run may read.",
        )


def _budget(selection: Selection, cells: ValueSource) -> tuple[int, int]:
    """The rows and cells a selection can reach, counted before any is read."""
    columns = len(selection.columns)
    match selection.rows:
        case RowRange(start=start, end=end):
            rows = end - start + 1
            return rows, rows * columns
        case RowSet(rows=members):
            return len(members), len(members) * columns
        case RowFilter():
            # A filter reads one cell per row the source has, to decide, and
            # then the columns of the rows that match.
            available = len(cells.rows())
            return available, available * (columns + 1)


def _evaluate(
    registered: RegisteredOperator[Any, Any], validated: BaseModel, cells: ValueSource
) -> BaseModel:
    """The operator, run.

    The operator's own refusals -- a selection that cannot be resolved, cells
    that disagree about their units -- are translated into this path's
    refusal, with the original kept as the cause.
    """
    try:
        return cast(BaseModel, registered.run(cast(Any, validated), cells))
    except SelectionRefusedError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.OPERATOR_REFUSED,
            f"the selection could not be resolved: {error}",
        ) from error
    except UnitDisagreementError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.OPERATOR_REFUSED,
            str(error),
        ) from error


def _build_manifest(
    *,
    source: Source,
    canonical: CanonicalPath,
    selection: Selection,
    operator: Operator[Any, Any],
    validated: BaseModel,
    result: BaseModel,
    recipe: str,
    workspace: Workspace,
) -> ReproducibilityManifest:
    """The manifest, which hashes the result and not the figure.

    The manifest is written before the figure, because the figure's chain
    names the manifest; writing the figure first would make one of the two
    hash a document that does not exist.
    """
    try:
        recipe_ref = read_recipe(workspace.selected_root, recipe)
    except ManifestRefusedError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.RECIPE_UNREADABLE,
            f"the recipe {recipe!r} could not be read: {error}",
        ) from error
    parameters = {
        name: value
        for name, value in _canonical_parameters(operator, validated).items()
        if not isinstance(getattr(validated, name, None), Selection)
    }
    try:
        return build_manifest(
            source=source,
            input_path=canonical.real_path,
            selection=selection,
            operator=operator_reference(operator),
            parameters=parameters,
            recipe=recipe_ref,
            result=result,
            environment=current_environment(),
        )
    except ManifestRefusedError as error:
        raise AnalysisRefusedError(
            AnalysisRefusal.MANIFEST_REFUSED,
            f"the manifest could not be built: {error}",
        ) from error


def _write_figure(
    *,
    workspace: Workspace,
    renderer: FigureRenderer,
    operator: Operator[Any, Any],
    result: BaseModel,
    manifest_receipt: ArtifactReceipt,
    run_token: str,
    created_at: datetime,
) -> ArtifactReceipt | None:
    """The figure, when the operator produced one.

    ``render()`` returning ``None`` is the renderer's own word for "this
    result is not a figure", and this path does not second-guess it.
    """
    payload = renderer.render(operator.operator_id, result)
    if payload is None:
        return None
    write = TaskOutputArea(workspace).write(_figure_key(operator, run_token), payload)
    relative_path = write.absolute_path.relative_to(workspace.selected_root).as_posix()
    return build_figure_receipt(
        manifest_receipt=manifest_receipt,
        relative_path=relative_path,
        content_sha256=write.content_hash,
        size_bytes=write.size_bytes,
        receipt_id=f"figure-{run_token}",
        created_at=created_at,
    )


def _manifest_key(operator: Operator[Any, Any], run_token: str) -> str:
    """Where the manifest goes, in the task's output area.

    The key carries the run's own token, so two runs of the same operator
    write two files rather than one file twice. The artefacts table is unique
    on (task, path, revision), and a path that repeated would make the second
    run a constraint violation rather than a second record.
    """
    return f"analysis/{operator.operator_id}/{run_token}.manifest.json"


def _figure_key(operator: Operator[Any, Any], run_token: str) -> str:
    """Where the figure goes, beside the manifest that names it."""
    return f"analysis/{operator.operator_id}/{run_token}.figure.svg"


# --------------------------------------------------------------------------- #
# The cells
# --------------------------------------------------------------------------- #


class _LedgerCells(ValueSource):
    """The current text of a material's cells, addressed by row and header.

    The ledger's own rows, indexed the way a selection addresses them: a
    physical row and a column's **header text**. A CSV carries both in its
    columns; a spreadsheet carries a sheet name and a cell reference, and its
    header is the text of row 1 in that column -- so the header is looked up
    rather than assumed.
    """

    def __init__(self, rows: Sequence[SourceTextRow], *, kind: LocatorKind) -> None:
        self._cells = _index_cells(rows, kind=kind)
        self._rows = tuple(sorted({row for row, _ in self._cells}))
        self._records_blank = records_blank_cells(
            SourceKind.CSV if kind is LocatorKind.CSV else SourceKind.XLSX
        )

    def text_at(self, address: CellAddress) -> str | None:
        """The text at *address*, or ``None`` when no cell was recorded there.

        ``None`` means "not recorded", which is not the same as "recorded and
        empty" -- and the difference is the whole reason the analysis layer
        counts blanks and absences separately.
        """
        return self._cells.get((address.row, address.column))

    def rows(self) -> tuple[int, ...]:
        """The physical rows this material has cells in, ascending."""
        return self._rows

    @property
    def records_blank_cells(self) -> bool:
        """Whether a cell the author left blank is visible here.

        A fact about the adapter, carried rather than branched on: the
        delimited adapter writes a unit for every cell it read, empty ones
        included, and the spreadsheet adapter writes one only for a cell that
        holds something.
        """
        return self._records_blank


def _index_cells(rows: Sequence[SourceTextRow], *, kind: LocatorKind) -> dict[tuple[int, str], str]:
    """The cells of a material, addressed by (physical row, header text).

    A workbook with more than one sheet is refused. A selection names a row
    and a header and no sheet, so a two-sheet workbook has addresses that
    cannot be told apart, and an address that cannot be told apart is an
    address nobody chose.
    """
    if kind is LocatorKind.CSV:
        return _index_csv(rows)
    return _index_xlsx(rows)


def _index_csv(rows: Sequence[SourceTextRow]) -> dict[tuple[int, str], str]:
    """A delimited material's cells: its rows carry the row and the header."""
    cells: dict[tuple[int, str], str] = {}
    for row in rows:
        if row.row_number is None or row.column_name is None:
            continue
        cells[(row.row_number, row.column_name)] = row.text
    return cells


def _index_xlsx(rows: Sequence[SourceTextRow]) -> dict[tuple[int, str], str]:
    """A spreadsheet's cells: the header is the text of row 1 in that column."""
    sheets = {row.sheet_name for row in rows if row.sheet_name is not None}
    if len(sheets) > 1:
        raise AnalysisRefusedError(
            AnalysisRefusal.SOURCE_AMBIGUOUS,
            f"the workbook holds {len(sheets)} sheets ({sorted(sheets)}), and a selection "
            "names a row and a header and no sheet. Two sheets can hold the same "
            "address, and an address that cannot be told apart is not one anybody "
            "chose.",
        )
    headers: dict[str, str] = {}
    placed: list[tuple[str, int, str]] = []
    for row in rows:
        if row.sheet_name is None or row.cell_ref is None:
            continue
        matched = _CELL_REF.match(row.cell_ref)
        if matched is None:
            continue
        letters = matched.group("letters")
        number = int(matched.group("row"))
        if number == 1:
            headers[letters] = row.text
        else:
            placed.append((letters, number, row.text))
    cells: dict[tuple[int, str], str] = {}
    for letters, number, text in placed:
        header = headers.get(letters)
        if header is None:
            continue
        cells[(number, header)] = text
    return cells


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _required(payload: Mapping[str, JsonValue], key: str) -> JsonValue:
    """A payload's field, or a refusal naming the one that is missing."""
    if key not in payload:
        raise _bad_payload(f"the selection payload has no {key!r}.")
    return payload[key]


def _non_empty(value: JsonValue, what: str) -> str:
    """A non-empty string, validated by the project's own primitive."""
    if not isinstance(value, str):
        raise _bad_payload(f"the selection's {what} is {type(value).__name__}, not text.")
    try:
        return _NON_EMPTY.validate_python(value)
    except ValidationError as error:
        raise _bad_payload(f"the selection's {what} is not a value: {error}") from error


def _hash(value: JsonValue) -> str:
    """A content hash, validated by the project's own primitive.

    ``Selection`` is a plain dataclass and so validates nothing about its
    hash, which means this check is the only one there is.
    """
    if not isinstance(value, str):
        raise _bad_payload(f"the selection's content hash is {type(value).__name__}, not text.")
    try:
        return _CONTENT_HASH.validate_python(value)
    except ValidationError as error:
        raise _bad_payload(f"the selection's content hash is not a hash: {error}") from error


def _row_number(payload: Mapping[str, JsonValue], key: str) -> int:
    """A row number, which is a positive integer and not a string."""
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise _bad_payload(f"a row range's {key!r} must be a whole number.")
    if value < 1:
        raise _bad_payload(f"a row range's {key!r} is {value}, and row 0 does not exist.")
    return value


def _bad_payload(detail: str) -> AnalysisRefusedError:
    """The refusal a malformed selection payload gets."""
    return AnalysisRefusedError(AnalysisRefusal.ARGUMENTS_INVALID, f"the selection: {detail}")
