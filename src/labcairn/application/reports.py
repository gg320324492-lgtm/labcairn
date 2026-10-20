"""Rendering a report: **declared**, not implemented.

LC-P1-11's T00 owns the report document model and T01 owns the four
renderers. The renderers are not in this build, and this operation says so
rather than pretending: a document model with no renderer renders nothing, and
an operation that returned one would be claiming a capability it does not
have.

**Why there is no implementation here.** A stub in the product is a lie about
a capability that exists. A ``render_report`` that returned an empty document,
or wrote a file with a placeholder in it, would let a caller — and a reader of
the report — believe a report had been produced. The report is the thing a
research task is judged by, and a placeholder report is worse than no report:
it can be mistaken for a finding.

So the operation is **declared** — its inputs, its capability, its resource and
its result are all fixed, so the three surfaces can be built against it and the
contract can be frozen — and the part that is missing is named, in the
docstring and in the refusal a caller receives.

What is already fixed
---------------------

* the capability is ``report.render``, whose argument model carries the
  report's key and the template it is rendered from, and nothing else;
* the resource is the report's own key in the task's output area, and the
  policy is asked about it before anything else happens — so the operation is
  already inside the capability model rather than beside it;
* the result is a receipt and a hash, because a report that was rendered and
  not recorded is a report nobody can check.

When T00 and T01 land, this operation becomes the call into the renderer, and
the capability check, the resource and the result are already the ones the
surfaces will use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.security.capabilities import CapabilityId


@dataclass(frozen=True, slots=True)
class ReportRequest:
    """What to render, and where the result goes.

    ``path`` is the report's key in the task's output area and
    ``template_id`` names the template it is rendered from. Those two are the
    whole of ``report.render``'s argument model, and the model is closed, so
    there is no third thing a caller could ask for.
    """

    path: str
    template_id: str


class ReportRendered(Result):
    """What rendering a report produced.

    The receipt is the record of it — the hash, the lineage, the revision —
    and it is what the store keeps, so a report that was rendered and not
    recorded does not exist.
    """

    receipt: ArtifactReceipt
    resource_key: str


def render_report(
    context: ApplicationContext,
    request: ReportRequest,
    *,
    now: datetime | None = None,
) -> ReportRendered:
    """Render the task's report.

    **This operation is not implemented.** LC-P1-11's T00 (the report document
    model) and T01 (the four renderers) have not landed, and this layer does
    not fake them.

    What *is* done is the part that does not depend on them: the capability's
    arguments are validated against the closed model, the report's key is
    admitted into the task's output area, and the policy is asked about it.
    So a caller that reaches this operation learns that the policy denies
    writing there rather than learning that the renderer is missing — and the
    refusal says which of the two it was.

    :raises ApplicationRefusedError: the policy denied the render, the
        arguments were not usable, or the renderer is not implemented yet.
    """
    # The renderer will want a clock; the refusal below happens before it does.
    del now
    resource = context.resource_in("output", request.path)
    consent.evaluate(
        context,
        capability=CapabilityId.REPORT_RENDER,
        arguments={"template_id": request.template_id},
        resource=resource,
    )
    raise ApplicationRefusedError(
        ApplicationRefusal.NOT_IMPLEMENTED,
        "rendering a report is declared but not implemented. The two pieces it "
        "is built on are LC-P1-11's report document model (T00) and its four "
        "renderers (T01); the renderers are not in this build, and a document "
        "model with no renderer renders nothing. The capability check above has "
        "already run, so a denial of report.render on "
        f"{request.path!r} would have been reported instead.",
    )


__all__ = ["ReportRendered", "ReportRequest", "render_report"]
