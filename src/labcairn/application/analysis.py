"""Running one analysis from a surface, and drawing its figure.

The run path is :func:`labcairn.analysis.service.run_analysis`, and it was written
before the application layer existed — the board records it as code the layer was
added on top of. It takes six collaborators (the store, the workspace, the policy,
the approval ledger, a renderer, and the recipe the figure is drawn from), and **a
surface must not assemble those**: what LC-P1-12 claims is that the CLI, the local
API and the workbench all call *one* layer, and a command that read its own files
and built its own renderer would be a second path to the same effect with its own
rules about what a read costs.

So this module is the seam. It resolves the recipe the request names, asks the
policy about the capability **on that resource as well as on the material** — the
consent binds the recipe's path by digest (ADR-0012 constraint 7), and a verdict
about the material alone would leave the file the figure is drawn from judged by
nobody — and calls the run path with the context's own collaborators. **It adds no
consent of its own**: the run path asks whether ``analysis.run`` is allowed and
spends the approval it was given, and a refusal from either is carried through with
its reason intact.

**Why the refusals keep their names.** ``labcairn.analysis.service`` has a
fifteen-member vocabulary of why a run did not happen, and a surface reads exactly
one refusal type. Mapping every member onto one of this layer's — rather than
flattening them into a single ``analysis_refused`` — is what keeps the layer's
promise that a caller branches on a *reason*: "no such operator" and "that
column's units contradict its header" ask different people for different things. The
mapping is closed by a test, so a refusal added to the run path cannot arrive at a
surface unmapped.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from labcairn.analysis.chart.recipe import ChartRecipe
from labcairn.analysis.manifest import ManifestRefusedError, ReproducibilityManifest, read_recipe
from labcairn.analysis.selection import Selection
from labcairn.analysis.service import (
    AnalysisRefusal,
    AnalysisRefusedError,
    AnalysisRequest,
    RunLimits,
    run_analysis,
)
from labcairn.application.consent import evaluate as evaluate_consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.security.capabilities import CapabilityId
from labcairn.sources.source import Source

if TYPE_CHECKING:
    from labcairn.analysis.service import FigureRenderer

#: Every refusal the run path can make, and the layer's name for it.
#:
#: **Closed, and checked closed**: a member of ``AnalysisRefusal`` with no row here
#: would reach a surface as an unmapped reason, and the layer would crash on the
#: lookup rather than invent a label for somebody else's refusal.
ANALYSIS_REFUSALS: Mapping[AnalysisRefusal, ApplicationRefusal] = {
    AnalysisRefusal.ARGUMENTS_INVALID: ApplicationRefusal.ARGUMENTS_INVALID,
    AnalysisRefusal.OPERATOR_NOT_REGISTERED: ApplicationRefusal.OPERATOR_NOT_REGISTERED,
    AnalysisRefusal.PATH_REFUSED: ApplicationRefusal.PATH_REFUSED,
    AnalysisRefusal.SOURCE_NOT_FOUND: ApplicationRefusal.SOURCE_NOT_FOUND,
    AnalysisRefusal.SOURCE_UNREADABLE: ApplicationRefusal.SOURCE_UNREADABLE,
    AnalysisRefusal.SOURCE_DRIFTED: ApplicationRefusal.SOURCE_DRIFTED,
    AnalysisRefusal.SOURCE_AMBIGUOUS: ApplicationRefusal.SOURCE_AMBIGUOUS,
    AnalysisRefusal.SELECTION_MISMATCH: ApplicationRefusal.SELECTION_MISMATCH,
    AnalysisRefusal.PERMISSION_DENIED: ApplicationRefusal.PERMISSION_DENIED,
    AnalysisRefusal.APPROVAL_MISSING: ApplicationRefusal.APPROVAL_MISSING,
    AnalysisRefusal.APPROVAL_REFUSED: ApplicationRefusal.APPROVAL_REFUSED,
    AnalysisRefusal.LIMITS_EXCEEDED: ApplicationRefusal.LIMITS_EXCEEDED,
    AnalysisRefusal.OPERATOR_REFUSED: ApplicationRefusal.OPERATOR_REFUSED,
    AnalysisRefusal.MANIFEST_REFUSED: ApplicationRefusal.MANIFEST_REFUSED,
    AnalysisRefusal.RECIPE_UNREADABLE: ApplicationRefusal.RECIPE_UNREADABLE,
}


@dataclass(frozen=True, slots=True)
class FigureRequest:
    """One figure run: what to analyse, from which recipe, under whose consent.

    ``root_id`` and ``path`` name the material **as the capability names it** — a
    key inside a named root — because the same key under two roots is two files,
    and the approval is bound to one of them. ``recipe`` is the chart recipe the
    figure is drawn from, workspace-relative, and it is part of the consented
    arguments rather than an aside beside them. ``operator_id`` and
    ``parameters`` are the operator's own arguments, validated by the operator.
    """

    root_id: str
    path: str
    operator_id: str
    recipe: str
    parameters: Mapping[str, Any]
    approval_id: ApprovalId


class FigureRun(Result):
    """What one analysis run produced, as a surface can serialise it.

    The manifest is the result's record and the receipts are the proof the files
    exist. ``figure_receipt`` is ``None`` exactly when the operator's result was
    not a figure, which is the renderer's word for it and not this layer's guess.
    """

    source: Source
    selection: Selection
    manifest: ReproducibilityManifest
    manifest_receipt: ArtifactReceipt
    figure_receipt: ArtifactReceipt | None


def _capability_arguments(request: FigureRequest) -> dict[str, Any]:
    """The consented arguments, in the one spelling the digest is taken over."""
    return {
        "path": request.path,
        "operator_id": request.operator_id,
        "recipe": request.recipe,
        "parameters": dict(request.parameters),
    }


def _the_recipe(context: ApplicationContext, request: FigureRequest) -> tuple[ChartRecipe, Any]:
    """The chart recipe, read through the permission boundary, with its reference.

    **The policy is asked about the run on the recipe's own resource.** The
    consent binds the recipe's path by digest, and a verdict that considered only
    the material would let a run whose recipe sits somewhere the policy never
    judged pass as allowed. Reading the file and hashing it are one act here — the
    bytes that are parsed are the bytes the manifest will name — and a recipe that
    is not a chart recipe is refused rather than read for what it might have been.
    """
    resource = context.resource_for(request.recipe)
    evaluate_consent(
        context,
        capability=CapabilityId.ANALYSIS_RUN,
        arguments=_capability_arguments(request),
        resource=resource,
    )
    try:
        data = resource.real_path.read_bytes()
        recipe_ref = read_recipe(context.workspace.selected_root, request.recipe)
    except (OSError, ManifestRefusedError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.RECIPE_UNREADABLE,
            f"the chart recipe {request.recipe!r} could not be read and hashed as one "
            f"file: {error}. A figure whose recipe nobody can read is a figure nobody "
            "can re-draw, and the manifest names its bytes by hash.",
        ) from error

    try:
        return ChartRecipe.model_validate_json(data), recipe_ref
    except ValidationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{request.recipe!r} is not a chart recipe this build can read: {error}. "
            "A recipe is a data, encoding and output document with no script beside it, "
            "and a document that is not one names no figure.",
        ) from error


def run_figure(
    context: ApplicationContext,
    request: FigureRequest,
    *,
    limits: RunLimits | None = None,
    renderer: FigureRenderer | None = None,
    now: datetime | None = None,
) -> FigureRun:
    """Run one operator and draw its figure, through the layer.

    The order is the run path's, stated here so a caller knows what has happened
    when a refusal arrives: the recipe is read and judged, the material's path is
    admitted into the named source root, the selection is built, the source is
    resolved (the ledger's row, the file's bytes, the readability), the policy is
    asked, the bounds are checked, **the consent is spent**, the operator is
    evaluated, the environment is prepared, the manifest is written, the figure is
    rendered and the receipts are recorded. Everything before the consent that
    refuses leaves the approval unspent.

    :param renderer: the figure's renderer, for a caller that owns one. Default:
        the analysis package's matplotlib renderer, built from the recipe this
        request named — which is why the recipe is read before the run rather
        than inside it.
    :raises ApplicationRefusedError: any refusal the run path makes, with the
        reason it named, plus ``recipe_unreadable`` and ``arguments_invalid`` for
        a recipe that cannot be read or is not a chart recipe.
    """
    moment = now if now is not None else datetime.now(UTC)
    recipe, recipe_ref = _the_recipe(context, request)
    drawn = renderer
    if drawn is None:
        # Imported here rather than at module level: matplotlib is imported
        # lazily by the whole analysis path (ADR-0012 constraint 5), and an
        # ``import`` at the top of this module would make every import of the
        # application layer cost a second of renderer.
        from labcairn.analysis.chart.render import MatplotlibFigureRenderer

        drawn = MatplotlibFigureRenderer(
            recipe=recipe,
            recipe_ref=recipe_ref,
            workspace_root=context.workspace.selected_root,
        )

    try:
        run = run_analysis(
            request=AnalysisRequest(
                approval_id=request.approval_id,
                root_id=request.root_id,
                arguments=_capability_arguments(request),
            ),
            store=context.store,
            workspace=context.workspace,
            policy=context.policy,
            ledger=context.ledger,
            renderer=drawn,
            limits=limits,
            now=moment,
        )
    except AnalysisRefusedError as error:
        # Indexed, not defaulted: a reason with no row above is a bug in that
        # table, and it must arrive as one rather than wearing somebody else's
        # label. The closure witness is what keeps this line unreachable.
        raise ApplicationRefusedError(
            ANALYSIS_REFUSALS[error.reason],
            str(error),
        ) from error

    return FigureRun(
        source=run.source,
        selection=run.selection,
        manifest=run.manifest,
        manifest_receipt=run.manifest_receipt,
        figure_receipt=run.figure_receipt,
    )


__all__ = ["ANALYSIS_REFUSALS", "FigureRequest", "FigureRun", "run_figure"]
