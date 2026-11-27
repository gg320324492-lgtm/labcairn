"""Rendering a report: the layer operation that joins the pieces.

LC-P1-11 built the report's parts one at a time — the document model (T00),
the four renderers (T01), the artefact manifest (T02), the revisions (T03),
the content checks (T04) and the document builder (T12) — and left one thing
out: **nothing called them.** This module is that call.

It lives in the layer because it is the one place where the parts have to be
joined. A report assembled by the CLI and another assembled by the API would
be two reports that could disagree about what the ledger says, and the whole
of LC-P1-11 is about a report being checkable against the material behind it.

The order, and why the order is the property
---------------------------------------------

**Nothing is written until everything is settled.** The capability check
comes first, because a policy denial and a missing renderer have different
remedies and a caller that is told the wrong one is sent to fix the wrong
thing. Then the report's material is gathered, the document is built, the
**sources its citations name are compared with the files on disk**, the
evidence gate judges the records the document states as established, the
content checks are run, and only then are the four forms rendered and the
revision written. A report that cannot be produced leaves **no file behind**:
a generated file that no receipt names is an artefact nothing can account
for, and a half-written report is worse than no report, because it looks like
a finding.

**The evidence gate is the last door, and it runs before the checks.**
------------------------------------------------------------

The gate is `labcairn.evidence.gate` — the same questions the work order's
acceptance names (status, identifier, re-verification, conflict), and the one
this operation found missing from them: whether the source still supports a
record the report states as established when the record's log holds no source
check to re-run. Until this operation called it, no surface did. It judges **the records
the document states as established**: the claims whose status is in
:data:`~labcairn.evidence.states.CITABLE_STATUSES`. An objection refuses the
report with ``report_evidence_refused``, names every finding and the record
it concerns, and leaves nothing written — because a report is the last place
a fabricated source or a contradicted number can be caught, and a report that
went out with its objection in an adjacent file would still be a report that
said it.

**The file is asked before the ledger is, because it moves first.** The gate's
index answers from the ledger, whose content hash is never refreshed, so it
cannot see a file edited on disk since ingestion. This operation therefore
opens every source the document's citations name, hashes it, and refuses the
report with the same ``report_evidence_refused`` when the file is not the
bytes the ledger describes. The two checks are the two links of one chain —
the file against the ledger here, the record against the ledger in the gate —
and neither may pass a source the other refuses. Refusing rather than writing
a stale receipt is deliberate: a ``STALE`` mark labels an artifact that was
current when it was made, and a report made after the move was never current.

**Why that scope, and not the task's whole set.** The gate's whole-task door
(:func:`~labcairn.evidence.gate.evaluate_task`) would refuse a report for a
record the report never quotes. A planned record is not carried at all, and a
superseded record is *kept by design* and skipped by the builder — so that
refusal could never be repaired: one correction would refuse every later
report of the task. That is a refusal the product does not promise, and it
would make the door one nobody could walk through.

**Why citable claims, and not every record the report carries.** The
document presents its other records *with their own status*: an ``extracted``
claim is printed as ``(extracted)`` and a conflicted record is disclosed as
unresolved. The gate's status finding on those records says exactly what the
report already prints — the report answers it in its own text. Refusing
there would make the graded claim (the claim that says how far it was
checked) and the unresolved-record disclosure unreachable, which is the whole
of the document model's honesty. What the report *does* claim beyond the
ledger's status label is that a citable record's verification still holds;
that is the claim the gate is asked about, and the three questions it can
answer only by asking the ledger and the source again — identifier resolved,
checks re-run, no contradicting record — are exactly the ones the report
cannot answer in its own text. So a finding on those refuses.

**What the gate did not judge is on the result.** :class:`ReportRendered`
carries the gate's own :class:`~labcairn.evidence.gate.GateResult` — the
records it judged — and ``unjudged_records``, the records the report names
but does not state as established. The gate judges evidence records and
nothing else: it does not judge a figure, a table, the snapshot or the
artefact links, and the content checks are what do. A report is not sound
because the gate passed it; it is not refused for what the gate did not
examine.

**The checks are run before the forms are rendered**, and the revision
machinery runs them again over the document it is about to write. The
machinery takes the four forms as **bytes** so that it does not have to know
how a form is produced — which is exactly why it cannot tell whether those
bytes belong to the document beside them. That property is therefore the
layer's to hold: the forms are rendered **from the document this operation
just built**, never carried in from anywhere else, and the checks are run
against that same document before a byte of it is rendered.

**The report is recorded, not merely produced.** The receipts the revision
wrote are put in the ledger and the ``artifact_recorded`` event is emitted,
in one transaction. A report that was rendered and not recorded does not
exist, and that is what :class:`ReportRendered` has always said.

The request's ``path``, and the revision's own paths
----------------------------------------------------

``ReportRequest.path`` is **the base the revision's paths hang from**. A
revision writes its six artefacts under ``report/v<N>/…`` — the canonical
document, the manifest and the four forms — and ``report`` is the directory
those paths sit in. So the request's path is that base, and it is the *only*
base: the revision machinery writes under one key, and a request naming any
other would be a request for a report that has nowhere to go. It is refused
rather than honoured, because a parameter that is accepted and ignored is a
parameter that lies.

Two guards make that safe rather than merely stated. The path is admitted
into the task's output area by :meth:`ApplicationContext.resource_in`, which
canonicalises it and refuses anything that escapes — so a caller cannot use
it to write outside the task's own area. And it is then required to be the
report's base, so the capability check is made about the very directory the
report goes into rather than about somewhere else.

What ``template_id`` is
-----------------------

**There is one template, and an unknown one is refused.** The report's
layout is not chosen at render time: the builder places the four kinds of
thing it carries in four sections, and the four renderers draw that model.
There is no second arrangement of them anywhere in the tree, and there is no
template registry — so naming a template is naming *the* one, and a name that
is not it is a name of nothing. The template is named rather than absent so
that the capability's argument model stays closed and so that a caller can
say which template it meant; it is not accepted-and-ignored, because the
layer knows the set and refuses a name outside it.

Where the chain's upstreams come from
-------------------------------------

The report's chain is a **flat ancestor closure**, and it reaches outside the
report's own files because the report's own files never change when the
material does. The material reaches it twice over, and the second route is
the one that does the work this operation cannot do by itself.

**The parts' material** comes from the ``upstreams`` this operation hands to
the manifest builder — and they come from **the ledger's own account of each
part**: the artefact receipt's ``derived_from``. That is the right source
because the ledger already holds it. A figure's receipt names the manifest
artefact that describes it and, through it, the input file the derivation
read; a table's receipt names what computed it. Both carry the material's
hash, which is what the one-hop staleness walk matches.

**The report's own material** — the sources its claims were read from — is
read out of the **document** by the manifest builder, and needs nothing from
here. It is the second route because a task with evidence records and no
analysis artefacts has no parts at all: its report carries claims and
nothing else, and the first route would name no material for it. A report
whose chain names nothing but its own files could not be marked stale when
the material moves, and nothing would notice.

What is refused, and how
------------------------

Every refusal is an :class:`ApplicationRefusedError` with a machine-readable
reason and a message that names what was wrong, so a surface catches one
exception and not two.

**The content refusals carry their own reason.** The builder's, the checks',
the manifest's, the revision's — and the layer's own, where a figure's
manifest or its recipe is not the one the ledger recorded — are all
``report_content_refused``, because they are one situation: the report's
content was refused, and nothing was written. They are **not**
``stage_failed``, because no stage ran and there is no execution to look at.
A stage that failed ran and failed, and the work may be worth retrying; a
report whose content was refused never ran, and the ledger is what has to
change. A caller that cannot tell those apart cannot tell whether to retry.

**The evidence gate's refusal is its own reason, because it is its own
repair.** ``report_evidence_refused`` says the records the report was about
to state as established no longer pass the ledger's and the source's own
questions: a verification that no longer holds, an identifier nothing
resolved, a record another contradicts, or a status the store never gave.
The content checks compare the *document* with the ledger as it is now; the
gate asks whether the *ledger's own account* is still true. The remedies are
different — revise the document, or repair the record and the source behind
it — and a caller told only "the report was refused" would not know which
door it hit.

The message names **what** refused and why — the check that refused and the
reason it gave, the builder and what it would not build, the artefact and
the hash it did not have — because a reason nobody can act on is the same as
no reason. The original is kept as the cause.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from pydantic import ValidationError
from sqlalchemy.engine import Connection

from labcairn.analysis.chart.recipe import ChartRecipe, RecipeRefusedError
from labcairn.analysis.manifest import ReproducibilityManifest
from labcairn.application import consent
from labcairn.application.artifacts import read_artifact
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.sources import list_sources
from labcairn.application.tasks import read_task_state
from labcairn.evidence.gate import GateResult, evaluate_records
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import CITABLE_STATUSES
from labcairn.evidence.store import load_task_records
from labcairn.reports.build import ReportBuildRefusedError, build_report_document
from labcairn.reports.checks import ReportRefusedError, check_report, ledger_reader
from labcairn.reports.manifest import ReportManifestRefusedError
from labcairn.reports.model import ReportDocument
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactReceipt,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.reports.render import render_docx, render_html, render_markdown, render_pdf
from labcairn.reports.revisions import (
    REPORT_DIR,
    ReportForm,
    ReportRevision,
    ReportRevisionRefusedError,
    write_report_revision,
)
from labcairn.runtime.event import EventType
from labcairn.security.approval import content_hash
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission
from labcairn.sources.source import Source, SourceAnchor

#: The report's key in the task's output area.
#:
#: It is the revision machinery's own constant rather than a spelling of this
#: module's, so that the key the layer checks against and the directory the
#: revision writes into cannot drift apart.
REPORT_KEY: Final[str] = REPORT_DIR

#: The one template a report is rendered from.
#:
#: The report's layout is fixed by the builder and drawn by the four
#: renderers, and there is no second arrangement of them to choose between.
DEFAULT_TEMPLATE_ID: Final[str] = "default"

#: Every template there is. Closed, because a template that is not in this set
#: names an arrangement nobody has written.
REPORT_TEMPLATES: Final[frozenset[str]] = frozenset({DEFAULT_TEMPLATE_ID})


@dataclass(frozen=True, slots=True)
class ReportRequest:
    """What to render, and where the result goes.

    ``path`` is the report's key in the task's output area — the base the
    revision's own paths hang from, and therefore the one key the revision
    machinery writes under. ``template_id`` names the template it is rendered
    from, and there is one of those. Those two are the whole of
    ``report.render``'s argument model, and the model is closed, so there is
    no third thing a caller could ask for.
    """

    path: str
    template_id: str


class ReportRendered(Result):
    """What rendering a report produced.

    The receipt is the record of it — the hash, the lineage, the revision —
    and it is what the store keeps, so a report that was rendered and not
    recorded does not exist.

    ``evidence_gate`` is the gate's own verdict, carried rather than assumed:
    which records the report states as established, and that they passed.
    ``unjudged_records`` is the other half of the same statement — the records
    the report names and the gate did **not** judge, because the report prints
    their own status rather than presenting them as established. Together they
    are every record the report carries, so a reader can see the gate's
    extent rather than infer it. The gate judges no figure, table, snapshot or
    link; those are the content checks' business, and a report is not sound
    because the gate passed it.
    """

    receipt: ArtifactReceipt
    resource_key: str
    #: The gate's verdict over the records the report states as established.
    evidence_gate: GateResult
    #: The records the report names and the gate did not judge: claims whose
    #: status the report prints (``extracted`` and the unresolved states), and
    #: the records it discloses. Sorted, so two renderings of one ledger agree.
    unjudged_records: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _FigureReadings:
    """What the layer read for the report's figures.

    Three things the builder cannot get for itself: the **manifest** that
    describes each figure, the **caption** that says what the figure shows,
    and the **interpretation** that says what it means.

    The caption and the interpretation are the author's own words, and they
    live in the figure's **chart recipe** — a file in the workspace, which is
    why reading one is a capability-checked read like any other. The
    interpretation is separate from the caption because the recipe keeps them
    apart: a caption says what is plotted and an interpretation says what it
    means, and marking the second while leaving the first alone is the whole
    of ADR-0004's A10 for a figure. An interpretation is **optional**, and a
    recipe with none contributes no block at all, because an absent
    interpretation and an empty one are different facts and only the first is
    true.
    """

    #: The reproducibility manifests, by the id of the artefact that holds them.
    manifests: Mapping[str, ReproducibilityManifest]
    #: The captions, by the figure artefact's id.
    captions: Mapping[str, str]
    #: The interpretations, by the figure artefact's id. Only the figures that
    #: have one.
    interpretations: Mapping[str, str]


def render_report(
    context: ApplicationContext,
    request: ReportRequest,
    *,
    now: datetime | None = None,
) -> ReportRendered:
    """Render the task's report, write it as a revision, and record it.

    The order is the property, and it is the order the module docstring
    gives: the capability check, then the gathering, then the document, then
    the evidence gate, then the checks, then the four forms, then the
    revision, then the records. A report that cannot be produced leaves no
    file behind.

    **The checks run twice, and that is deliberate.** They run here, over
    the document this operation has just built, and the same checks are
    handed to the revision machinery as its ``verify``. The two are not
    redundant, because they are at different points:

    * the layer's own run happens **before the four forms are rendered**, so
      a document the checks refuse is not drawn at all — and the four forms
      are bytes, so a refusal that arrived after them would have produced
      bytes of a report that may not exist;
    * the machinery's run happens **inside the write**, over the document it
      is about to write, so the machinery itself refuses a revision of a
      document the checks refuse — which is a property of the machinery and
      not of this layer.

    Each hold is enough on its own, and that is the point. **If a future
    change removes one of them, the other still holds the line** — a reader
    who wonders why the checks are run twice should find that, because it is
    the answer, and because it is worth knowing that neither one is load
    bearing on its own. Removing both would let a report the checks refuse
    be written.

    :param context: everything the operation is given.
    :param request: the report's key and the template it is rendered from.
    :param now: the moment the document is a view of. Passed in rather than
        read, so that "when was this made" is a fact and not a
        re-derivation.
    :returns: the canonical document's receipt and the report's key.
    :raises ApplicationRefusedError: the policy denied the render or asked
        about it, the request named something that does not exist, or the
        report's content was refused — in which case nothing was written.
    """
    moment = now if now is not None else datetime.now(UTC)

    # 1. The capability check, on the resource the request names, before
    #    anything is read or written.
    resource = context.resource_in("output", request.path)
    authorisation = consent.evaluate(
        context,
        capability=CapabilityId.REPORT_RENDER,
        arguments={"template_id": request.template_id},
        resource=resource,
    )
    if authorisation.permission is Permission.ASK:
        raise ApplicationRefusedError(
            ApplicationRefusal.POLICY_ASKED,
            f"the policy asked about {CapabilityId.REPORT_RENDER.value} on "
            f"{resource.resolved_key!r}, and no approval was supplied. A report "
            "the policy asked about needs consent: grant the approval and render "
            "the report again.",
        )

    # 2. The request's own two claims, checked against what there is.
    _refuse_an_unknown_template(request.template_id)
    _refuse_a_path_that_is_not_the_report(request.path)

    # 3. What the report is made of.
    state = read_task_state(context)
    receipts = state.artifacts
    sources = tuple(view.source for view in list_sources(context))
    connection = context.store.session.connection()
    records = load_task_records(connection, str(context.task_id))
    index = LabCairnIndex(connection)
    anchors = _the_anchors(records, index=index)
    readings = _the_figure_readings(context, receipts)

    # 4. The document.
    document = _build_the_document(
        title=state.task.title,
        moment=moment,
        records=records,
        receipts=receipts,
        sources=sources,
        anchors=anchors,
        readings=readings,
    )

    # 5a. The file behind every citation, against the ledger's account of it.
    #     Asked before the gate because it is the question the ledger cannot
    #     answer: the ledger's hash is never refreshed, so only the file can
    #     say whether the material has moved since it was ingested.
    _refuse_moved_material(context, document=document, sources=sources)

    # 5b. The evidence gate, over the records the document states as
    #     established -- before any check reads the ledger again, because the
    #     gate is what asks whether that ledger's own account is still true.
    gate = _the_evidence_gate(
        connection, task_id=str(context.task_id), index=index, document=document
    )

    # 6. The checks, before the first byte of the report is rendered.
    _check_the_document(document, context, connection=connection, index=index)

    # 7. The four forms, rendered from the document just built.
    forms = _the_four_forms(document)

    # 8. The revision: the canonical document, the manifest and the four
    #    forms, written under this task's own revision paths.
    revision = _write_the_revision(
        context,
        document=document,
        forms=forms,
        connection=connection,
        index=index,
        receipts=receipts,
        moment=moment,
    )

    # 9. The records: the receipts in the ledger and the event that says so.
    _record_the_revision(context, revision, moment=moment)

    # 10. The result, with the gate's extent on it.
    return ReportRendered(
        receipt=revision.document,
        resource_key=resource.resolved_key,
        evidence_gate=gate.result,
        unjudged_records=gate.unjudged,
    )


# --------------------------------------------------------------------------- #
# the request
# --------------------------------------------------------------------------- #


def _refuse_an_unknown_template(template_id: str) -> None:
    """Refuse a template nobody has written.

    The layer knows the set, so a name outside it is refused rather than
    accepted and ignored. A parameter that is accepted and ignored is a
    parameter that lies, and a caller that was told "default" had been
    rendered would have no way to know it was not.
    """
    if template_id in REPORT_TEMPLATES:
        return
    raise ApplicationRefusedError(
        ApplicationRefusal.ARGUMENTS_INVALID,
        f"the template {template_id!r} is not one there is. The templates are "
        f"{sorted(REPORT_TEMPLATES)}: the report's layout is fixed by the "
        "document builder and drawn by the four renderers, and there is no "
        "second arrangement of them to choose between.",
    )


def _refuse_a_path_that_is_not_the_report(path: str) -> None:
    """Refuse a report key that is not the one the revisions are written under.

    The revision machinery writes under one key — ``report``, with the
    revisions beneath it — so a request naming any other is asking for a
    report that has nowhere to go. Honouring it is not possible without
    changing the machinery, and quietly rendering somewhere else would be
    worse: the caller would be told its report was at a key it is not at.
    """
    if path == REPORT_KEY:
        return
    raise ApplicationRefusedError(
        ApplicationRefusal.PATH_REFUSED,
        f"the report's key in the task's output area is {REPORT_KEY!r}, and "
        f"{path!r} is not it. The revisions are written under {REPORT_KEY!r} — "
        f"one directory per revision beneath it — so a report named anything "
        "else has nowhere to go.",
    )


# --------------------------------------------------------------------------- #
# gathering
# --------------------------------------------------------------------------- #


def _the_anchors(
    records: tuple[EvidenceRecord, ...], *, index: LabCairnIndex
) -> dict[str, SourceAnchor]:
    """The anchors the task's records name, and the addresses behind them.

    A record carries anchor *ids* and a citation needs the address behind
    them, so the layer resolves them through the index. An anchor the ledger
    does not hold is left out rather than invented, and the builder refuses
    the record that names it — which is the honest place for that refusal,
    because the builder says which record and which anchor.
    """
    anchors: dict[str, SourceAnchor] = {}
    for record in records:
        for anchor_id in record.anchor_ids:
            if anchor_id in anchors:
                continue
            anchor = index.load_anchor(anchor_id)
            if anchor is not None:
                anchors[anchor_id] = anchor
    return anchors


def _the_figure_readings(
    context: ApplicationContext, receipts: tuple[ArtifactReceipt, ...]
) -> _FigureReadings:
    """The manifests, captions and interpretations of the task's figures.

    Three reads per figure, in the order the figure's own chain gives them:
    the **manifest artefact** the figure names, which is the figure's own
    derivation; the **manifest** that artefact holds, which names the recipe;
    and the **recipe**, which holds the caption and the interpretation.

    The manifest artefact is found through the figure's chain rather than
    guessed: a figure is derived from its manifest and from everything the
    manifest was derived from, so the manifest is the one link of kind
    ``artifact`` in that chain, and a chain that does not say which manifest
    describes the figure describes no derivation at all.
    """
    by_id = {receipt.receipt_id: receipt for receipt in receipts}
    manifests: dict[str, ReproducibilityManifest] = {}
    captions: dict[str, str] = {}
    interpretations: dict[str, str] = {}

    for receipt in receipts:
        if receipt.kind is not ArtifactKind.FIGURE:
            continue
        manifest_receipt = _the_manifest_artefact(receipt, by_id=by_id)
        manifest = _read_the_manifest(context, manifest_receipt)
        manifests[manifest_receipt.receipt_id] = manifest
        recipe = _read_the_recipe(context, manifest, figure=receipt)
        captions[receipt.receipt_id] = recipe.encoding.caption
        interpretation = recipe.encoding.interpretation
        if interpretation is not None:
            interpretations[receipt.receipt_id] = interpretation

    return _FigureReadings(manifests=manifests, captions=captions, interpretations=interpretations)


def _the_manifest_artefact(
    receipt: ArtifactReceipt, *, by_id: Mapping[str, ArtifactReceipt]
) -> ArtifactReceipt:
    """The manifest artefact the figure names, and only that one.

    The same rule the builder applies, and for the same reason: the figure's
    chain is read rather than guessed at, and a chain that names no manifest
    or more than one describes no derivation at all. The layer needs the
    artefact before the builder runs — the builder looks the manifest **up**
    by the artefact's id — so the lookup is made here and the builder checks
    it again.
    """
    candidates = [
        named
        for link in receipt.derived_from
        if link.target_kind is DerivationTargetKind.ARTIFACT
        for named in (by_id.get(link.target_id),)
        if named is not None and named.kind is ArtifactKind.MANIFEST
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise ApplicationRefusedError(
        ApplicationRefusal.ARTIFACT_NOT_FOUND,
        f"the figure {receipt.receipt_id!r} names {len(candidates)} manifest "
        "artefacts in its own chain, where it must name exactly one. A figure's "
        "lineage runs file, result, manifest, figure, and a chain that does not "
        "say which manifest describes it describes no derivation at all.",
    )


def _read_the_manifest(
    context: ApplicationContext, manifest_receipt: ArtifactReceipt
) -> ReproducibilityManifest:
    """The manifest the artefact holds, read back from the artefact's own bytes.

    The bytes on disk are hashed and compared with the receipt's own hash
    before the manifest is parsed, so the manifest the report carries is the
    one the ledger recorded and not some other manifest that happens to parse.
    """
    content = read_artifact(context, manifest_receipt.receipt_id)

    observed = hashlib.sha256(content.content).hexdigest()
    if observed != manifest_receipt.content_sha256:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the manifest artefact {manifest_receipt.receipt_id!r} is not the "
            f"artefact the ledger recorded: the receipt says bytes that hash to "
            f"{manifest_receipt.content_sha256}, but the file at "
            f"{manifest_receipt.relative_path!r} hashes to {observed}. A manifest "
            "that is not the artefact's own describes a derivation nobody can "
            "reproduce.",
        )
    try:
        return ReproducibilityManifest.model_validate_json(content.content)
    except ValidationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the manifest artefact {manifest_receipt.receipt_id!r} does not hold a "
            f"reproducibility manifest: {error}. A figure whose derivation cannot "
            "be read is a figure nobody can check.",
        ) from error


def _read_the_recipe(
    context: ApplicationContext,
    manifest: ReproducibilityManifest,
    *,
    figure: ArtifactReceipt,
) -> ChartRecipe:
    """The figure's chart recipe: the caption, and the interpretation if it has one.

    The recipe is a **file in the workspace**, so reading it is a
    capability-checked read like any other, and the path it is read from is
    the one the manifest names. The file's bytes are hashed and compared with
    the manifest's record of them: a recipe that has changed under the
    manifest is a recipe the manifest does not describe, and the caption it
    holds would not be the caption the figure was drawn from.

    A recipe that is not a **chart** recipe is refused rather than read for
    what it might have. The caption is the author's words about what is
    plotted, and they live in the chart recipe; a recipe with no encoding
    names no figure, and a report that composed a caption of its own would be
    a report whose caption changes with the format.
    """
    reference = manifest.recipe
    resource = context.resource_for(reference.relative_path)
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={},
        resource=resource,
    )
    try:
        data = resource.real_path.read_bytes()
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the recipe of the figure {figure.receipt_id!r} is at "
            f"{reference.relative_path!r}, and its bytes could not be read: "
            f"{error}. A figure whose recipe nobody can read is a figure whose "
            "caption nobody can check.",
        ) from error

    observed = hashlib.sha256(data).hexdigest()
    if observed != reference.content_sha256:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the recipe of the figure {figure.receipt_id!r} is not the recipe the "
            f"manifest names: the file at {reference.relative_path!r} hashes to "
            f"{observed}, and the manifest records bytes that hash to "
            f"{reference.content_sha256}. The recipe the manifest describes is not "
            "the recipe on disk, and the caption would not be the one the figure "
            "was drawn from.",
        )

    try:
        return ChartRecipe.model_validate_json(data)
    except (ValidationError, RecipeRefusedError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the recipe of the figure {figure.receipt_id!r} is at "
            f"{reference.relative_path!r}, and it is not a chart recipe: {error}. A "
            "figure's caption is the author's words and lives in the chart recipe, "
            "and a report that composed one would be a report whose caption "
            "changes with the format.",
        ) from error


# --------------------------------------------------------------------------- #
# the document, the checks and the forms
# --------------------------------------------------------------------------- #


def _build_the_document(
    *,
    title: str,
    moment: datetime,
    records: tuple[EvidenceRecord, ...],
    receipts: tuple[ArtifactReceipt, ...],
    sources: tuple[Source, ...],
    anchors: Mapping[str, SourceAnchor],
    readings: _FigureReadings,
) -> ReportDocument:
    """The report's document, built from what the task has.

    The title is the **task's** title, because it is the only content the
    request does not carry and the only words a caller has already written:
    a title is content, and neither the builder nor this layer writes
    content.

    The builder refuses rather than producing a document with a hole in it,
    and its refusal is translated into the layer's one refusal type — the
    operation may not raise two.
    """
    try:
        return build_report_document(
            title=title,
            as_of=moment,
            records=records,
            artifacts=receipts,
            sources=sources,
            anchors=anchors,
            manifests=readings.manifests,
            captions=readings.captions,
            interpretations=readings.interpretations,
        )
    except ReportBuildRefusedError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the document builder refused the report: {error}. Nothing was written: "
            "a report the ledger cannot support must not be written with a hole "
            "in it.",
        ) from error


# --------------------------------------------------------------------------- #
# the material the ledger cannot see
# --------------------------------------------------------------------------- #


def _refuse_moved_material(
    context: ApplicationContext,
    *,
    document: ReportDocument,
    sources: tuple[Source, ...],
) -> None:
    """Refuse the report when a cited source is not the file the ledger describes.

    **Why the render and not the gate.** The gate's index answers from the
    ledger, and the ledger's ``content_sha256`` is the hash the material had
    when it was ingested -- never refreshed (ADR-0004 I4). A file edited on
    disk since then therefore looks current to every account built only from
    ledger rows, and a report would be written with a receipt that says
    ``current`` over bytes that are gone. The source, in the end, is the file;
    this is the one place in the render that opens it, hashes it and compares.

    **Every source the document's claims cite**, not only the ones behind
    established claims: the receipt's chain names a link per cited source
    (:func:`labcairn.reports.manifest.build_report_manifest` reads them out of
    the same footnotes), and the receipt's ``current`` is a statement about
    every link it names. A report written while one named source had moved
    would be a receipt that is current only by not looking.

    **Refused, not marked stale.** A ``STALE`` receipt is the mark for an
    artifact that was current when it was made and whose input moved since; a
    report made *after* the move was never current, and its body would still
    state its claims as established. So nothing is written, and the refusal
    names each source, the bytes the ledger holds and the bytes the file has.

    The comparison is with the **ledger's** hash, not the record's: the gate
    asks the record against the ledger, and this asks the ledger against the
    file. The two are the links of one chain, and a record whose binding holds
    against a ledger that no longer describes the file is still a claim on
    bytes nobody can produce. Reading here is hashing only -- the bytes are
    never parsed and nothing of the material enters the report -- and it is
    the act the approval machinery already performs on every bound source
    (:func:`labcairn.security.approval.sources_intact`).
    """
    by_id = {source.source_id: source for source in sources}
    footnotes = {footnote.footnote_id: footnote for footnote in document.footnotes}
    cited: set[str] = set()
    for claim in document.claims:
        for footnote_id in claim.footnote_ids:
            footnote = footnotes.get(footnote_id)
            if footnote is not None:
                cited.add(footnote.source_id)

    moved: list[str] = []
    for source_id in sorted(cited):
        source = by_id.get(source_id)
        if source is None:
            # The builder refuses a claim whose citation the report does not
            # carry, so a document that reaches here names only sources in
            # this list. An absent row is not this check's question.
            continue
        try:
            resource = context.resource_for(source.relative_path)
            observed = content_hash(resource.real_path)
        except ApplicationRefusedError as error:
            moved.append(f"{source_id!r} ({source.relative_path}) is not addressable: {error}")
            continue
        except OSError as error:
            moved.append(f"{source_id!r} ({source.relative_path}) cannot be read: {error}")
            continue
        if observed != source.content_sha256:
            moved.append(
                f"{source_id!r} ({source.relative_path}) has moved: the ledger holds "
                f"{source.content_sha256}, and the file now hashes to {observed}"
            )
    if not moved:
        return
    raise ApplicationRefusedError(
        ApplicationRefusal.REPORT_EVIDENCE_REFUSED,
        f"{len(moved)} source(s) the report cites are not the bytes the ledger "
        f"describes: {'; '.join(moved)}. ADR-0004 I4 invalidates a record whose "
        "source has moved rather than refreshing it, so the report is refused "
        "before it is written: a receipt that said 'current' over these bytes "
        "would be a claim about the ledger alone, and the report's claims rest on "
        "the source. Nothing was written. Ingest the material again, then "
        "re-verify or re-attest the claims it carries.",
    )


@dataclass(frozen=True, slots=True)
class _EvidenceGate:
    """The gate's answer over the report, and the records it did not judge.

    A pair rather than one field because the two are one statement: the gate
    judged *these* records and passed them, and *those* records the report
    names are outside the gate. Carrying only the verdict would let a reader
    take "passed" for "the whole report was judged", which is the inference
    the module docstring says the result must prevent.
    """

    #: The gate's own result, over the records the report states as established.
    result: GateResult
    #: The records the report names and the gate did not judge, sorted.
    unjudged: tuple[str, ...]


def _the_evidence_gate(
    connection: Connection,
    *,
    task_id: str,
    index: LabCairnIndex,
    document: ReportDocument,
) -> _EvidenceGate:
    """Run the evidence gate over the records the document states as established.

    **Which records, and why exactly these.** A claim whose status is in
    :data:`~labcairn.evidence.states.CITABLE_STATUSES` is the report's own
    assertion that the ledger's verification stands behind the sentence; that
    is the assertion the gate re-asks the ledger and the source about. A claim
    with any other status is printed *with that status* — the document's
    ``(extracted)`` — and a disclosure is printed as unresolved, so the
    gate's status finding on those records is a finding the report's own text
    already states. Refusing there would delete the graded claim and the
    disclosure, and neither is a claim that the verification holds.

    The set is read from the **document**, not recomputed from the gathered
    records: the document is the thing that will be rendered and checked, and
    a second computation of "which of these are established" is a second rule
    that can drift from the builder's.

    A finding refuses the report. The gate refuses the set rather than the
    record — a report may not drop the failing sentence and keep the rest —
    and the message names every finding and the record it concerns, because a
    refusal that said only "the gate refused" would send the reader hunting
    through a ledger.
    """
    judged = tuple(
        claim.record.record_id
        for claim in document.claims
        if claim.record.status in CITABLE_STATUSES
    )
    result = evaluate_records(connection, task_id=task_id, index=index, evidence_ids=judged)
    if not result.passed:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_EVIDENCE_REFUSED, _the_gate_s_refusal(result)
        )
    unjudged = tuple(
        sorted(
            [
                claim.record.record_id
                for claim in document.claims
                if claim.record.status not in CITABLE_STATUSES
            ]
            + [disclosure.record.record_id for disclosure in document.unresolved_records]
        )
    )
    return _EvidenceGate(result=result, unjudged=unjudged)


def _the_gate_s_refusal(result: GateResult) -> str:
    """Every objection the gate raised, with the record it is about.

    The message is the actionable shape: one clause per finding, each naming
    the record, the kind of objection, and the gate's own sentence about what
    it found. The gate reports all of its objections rather than the first, so
    the refusal does too — a caller who fixes one and is refused again by the
    next has been made to pay for the same mistake twice.
    """
    objections = "; ".join(
        f"{finding.evidence_id} ({finding.kind}): {finding.reason}" for finding in result.findings
    )
    return (
        "the evidence gate refused the report before anything was written: "
        f"{len(result.findings)} objection(s) over the {len(result.considered)} "
        f"record(s) the report states as established. {objections}. Nothing was "
        "written: a report may not state a record the ledger and the source no "
        "longer support, and the gate refuses the set rather than the record."
    )


def _check_the_document(
    document: ReportDocument,
    context: ApplicationContext,
    *,
    connection: Connection,
    index: LabCairnIndex,
) -> None:
    """Run the content checks over the document, and refuse if they do.

    The checks read the **ledger** and the **index**, not the document's own
    copy of either: a check that compared the model's copy of a record with
    the model's copy of the same record would be comparing the thing under
    test with itself.

    The root the artefacts are read under is the **selected root**, because
    that is what a receipt's workspace-relative path is relative to.
    """
    try:
        check_report(
            document,
            ledger=ledger_reader(connection),
            index=index,
            workspace_root=context.workspace.selected_root,
        )
    except ReportRefusedError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the {error.check} check refused the report: {error.reason}. Nothing "
            "was written: a report that says something the ledger does not support "
            "must not be written at all.",
        ) from error


def _the_four_forms(document: ReportDocument) -> dict[ReportForm, bytes]:
    """The four forms, rendered from this document.

    Rendered **here**, from the document that was just built and checked, and
    not carried in from anywhere else. The revision machinery takes the forms
    as bytes so that it does not have to know how a form is produced — which
    is exactly why it cannot tell whether those bytes belong to the document
    beside them, and why this is the place the four forms and the canonical
    document are held to saying the same thing.
    """
    return {
        ReportForm.MARKDOWN: render_markdown(document),
        ReportForm.HTML: render_html(document),
        ReportForm.DOCX: render_docx(document),
        ReportForm.PDF: render_pdf(document),
    }


# --------------------------------------------------------------------------- #
# the revision
# --------------------------------------------------------------------------- #


def _the_upstreams(
    document: ReportDocument, receipts: tuple[ArtifactReceipt, ...]
) -> dict[str, tuple[DerivationRef, ...]]:
    """What produced each part of the report, by part id.

    **The ledger's own account**: the artefact receipt's ``derived_from``.
    A figure's receipt names the manifest artefact that describes it and,
    through it, the input file the derivation read; a table's receipt names
    what computed it. Both carry the material's hash, and the material's hash
    is what the one-hop staleness walk matches — so this is what lets a
    report with parts be marked stale when the material moves.

    This is the **parts'** material, and it is not the whole of it: a report
    with claims and no figure and no table has no part to name, and its
    material is the source its claims were read from. The manifest builder
    reads that out of the document, so a report of that shape is marked
    stale as well.

    The part is matched to its receipt by the path and the hash the document
    records, both of which the builder copied out of the receipt, and by the
    revision: the newest emission of a path is the one a report carries, and
    a report that carried two would show the same figure twice.
    """
    newest: dict[str, ArtifactReceipt] = {}
    for receipt in receipts:
        current = newest.get(receipt.relative_path)
        if current is None or receipt.revision > current.revision:
            newest[receipt.relative_path] = receipt

    upstreams: dict[str, tuple[DerivationRef, ...]] = {}
    for part_id, relative_path, content_sha256 in _the_parts(document):
        part_receipt = newest.get(relative_path)
        if part_receipt is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.REPORT_CONTENT_REFUSED,
                f"the part {part_id!r} is not an artefact the ledger holds: the "
                f"report carries it at {relative_path!r}, and the ledger holds no "
                "artefact at that path. A part the ledger does not hold is a part "
                "nobody can say is current.",
            )
        if part_receipt.content_sha256 != content_sha256:
            raise ApplicationRefusedError(
                ApplicationRefusal.REPORT_CONTENT_REFUSED,
                f"the part {part_id!r} is not the artefact the ledger recorded: the "
                f"report carries bytes at {relative_path!r} that hash to "
                f"{content_sha256}, and the ledger's artefact at that path hashes "
                f"to {part_receipt.content_sha256}. The part in the report is not "
                "the one the ledger recorded.",
            )
        upstreams[part_id] = part_receipt.derived_from
    return upstreams


def _the_parts(document: ReportDocument) -> tuple[tuple[str, str, str], ...]:
    """Every part the document carries, with the path and hash it records."""
    parts = [
        (figure.figure_id, figure.relative_path, figure.content_sha256)
        for figure in document.figures
    ]
    parts.extend(
        (table.table_id, table.relative_path, table.content_sha256) for table in document.tables
    )
    return tuple(parts)


def _write_the_revision(
    context: ApplicationContext,
    *,
    document: ReportDocument,
    forms: Mapping[ReportForm, bytes],
    connection: Connection,
    index: LabCairnIndex,
    receipts: tuple[ArtifactReceipt, ...],
    moment: datetime,
) -> ReportRevision:
    """Write this revision of the report, and return what it wrote.

    The revision number is left to the machinery, which makes it one beyond
    the highest this task's output area already holds: a second render is a
    **new revision** with new files, and the first revision's files are
    never touched.

    The checks are handed over as the ``verify`` callable as well, so that
    the machinery holds the property too — it takes the forms as bytes and
    cannot tell whether they belong to the document beside them, but it can
    still refuse to write a document the checks refuse.
    """
    verify = _the_verifier(context, connection=connection, index=index)
    try:
        return write_report_revision(
            context.workspace,
            document=document,
            forms=forms,
            verify=verify,
            upstreams=_the_upstreams(document, receipts),
            created_at=moment,
        )
    except (ReportRevisionRefusedError, ReportManifestRefusedError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.REPORT_CONTENT_REFUSED,
            f"the report was refused before it could be written as a revision: "
            f"{error}. Nothing was written.",
        ) from error


def _the_verifier(
    context: ApplicationContext, *, connection: Connection, index: LabCairnIndex
) -> Callable[[ReportDocument], None]:
    """The checks, as the callable the revision machinery asks for.

    A callable that **raises** if the document says anything the ledger does
    not support, which is what the machinery's ``verify`` is.
    """

    def verify(document: ReportDocument) -> None:
        _check_the_document(document, context, connection=connection, index=index)

    return verify


def _record_the_revision(
    context: ApplicationContext, revision: ReportRevision, *, moment: datetime
) -> None:
    """Put the revision's receipts in the ledger, and say so in the log.

    One transaction, because they are one fact: the report was rendered, here
    is what it produced. The event is what makes the report *findable* —
    without it the receipts would be rows nobody had been told about.
    """
    with context.store.unit(context.task_id) as work:
        for receipt in revision.receipts:
            work.put_artifact(receipt)
        work.emit(EventType.ARTIFACT_RECORDED, occurred_at=moment)


__all__ = [
    "DEFAULT_TEMPLATE_ID",
    "REPORT_KEY",
    "REPORT_TEMPLATES",
    "ReportRendered",
    "ReportRequest",
    "render_report",
]
