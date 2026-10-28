"""The application layer: the operations the CLI, the API and the UI all call.

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.5 is the requirement: *"CLI/
API/UI call same application layer"*, and the acceptance clause behind it is
*"CLI and UI show identical Task state"*. A property like that is not made by
three implementations agreeing; it is made by there being one implementation
for the three to call.

What the layer is for
---------------------

**It is the only way to the task state.** Everything here reads and writes
through :class:`~labcairn.db.repository.TaskStore`, so a surface that holds an
:class:`~labcairn.application.context.ApplicationContext` can call the layer and
a surface that does not cannot reach the task at all. That is what makes it a
seam rather than a convenience: a guard applied to an operation applies to
every caller, because there is only one caller path.

**Every operation goes through the capability model.** The capability id, the
policy verdict and the approval ledger's ``consume`` — with the arguments'
digest recomputed at the moment of use — are applied in
:mod:`labcairn.application.consent`, once, for every operation. So a surface
cannot grant itself a permission the other surfaces would not, and the
question "may this happen?" is answered in one place.

**Every operation returns data.** A CLI's ``--json`` output and an API's
response body are the same model, rendered the same way, because
``docs/ARCHITECTURE.md`` says formatting must never be load-bearing for a
machine-readable command.

One refusal, one shape
-----------------------

Every refusal raises :class:`~labcairn.application.refusal.ApplicationRefusedError`
with a machine-readable reason and a message that names what was wrong. A
surface renders it with :meth:`~labcairn.application.refusal.ApplicationRefusedError.to_payload`
and does not need to know which operation produced it.

The operations
--------------

=========================  ===========================================
Operation                  Capability
=========================  ===========================================
``create_task``            ``fs.write``
``read_task_state``        ``fs.read``
``read_events``            ``fs.read``
``list_tasks``             ``fs.list``
``run_stage``              the caller's
``read_plan``              ``fs.read``
``read_steps``             ``fs.read``
``list_sources``           ``source.inventory``
``inspect_source``         ``source.inventory``
``list_source_addresses``  ``source.inventory``
``record_claim``           ``source.inventory``
``ingest_material``        ``source.inventory``
``list_artifacts``         ``fs.list``
``read_artifact``          ``fs.read``
``request_approval``       the caller's
``grant_approval``         — (it *is* the consent)
``consume_approval``       the approved one
``render_report``          ``report.render``
``run_figure``             ``analysis.run``
=========================  ===========================================
"""

from __future__ import annotations

from labcairn.application.analysis import (
    FigureRequest,
    FigureRun,
    run_figure,
)
from labcairn.application.approvals import (
    ApprovalConsumed,
    ApprovalGranted,
    ApprovalRequest,
    ApprovalRequested,
    ApprovalUse,
    consume_approval,
    grant_approval,
    request_approval,
)
from labcairn.application.artifacts import (
    ArtifactContent,
    ArtifactView,
    list_artifacts,
    read_artifact,
)
from labcairn.application.context import ApplicationContext
from labcairn.application.events import EventPage, read_events
from labcairn.application.evidence import (
    ClaimRecorded,
    ClaimRequest,
    SourceAddress,
    list_source_addresses,
    record_claim,
)
from labcairn.application.material_ingestion import (
    IngestedFile,
    IngestFailure,
    MaterialIngested,
    ingest_material,
)
from labcairn.application.models import Result
from labcairn.application.recovery import (
    describe_abandoned,
    reconcile_abandoned,
    resolve_abandoned,
)
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.reports import (
    DEFAULT_TEMPLATE_ID,
    REPORT_TEMPLATES,
    ReportRendered,
    ReportRequest,
    render_report,
)
from labcairn.application.sources import SourceView, inspect_source, list_sources
from labcairn.application.stages import (
    PlanStage,
    StageOutcome,
    StageRequest,
    StageRun,
    StageWork,
    TaskPlan,
    TaskStep,
    read_plan,
    read_steps,
    run_stage,
)
from labcairn.application.tasks import (
    TaskCreated,
    TaskState,
    create_task,
    list_tasks,
    read_task_state,
)

__all__ = [
    "DEFAULT_TEMPLATE_ID",
    "REPORT_TEMPLATES",
    "ApplicationContext",
    "ApplicationRefusal",
    "ApplicationRefusedError",
    "ApprovalConsumed",
    "ApprovalGranted",
    "ApprovalRequest",
    "ApprovalRequested",
    "ApprovalUse",
    "ArtifactContent",
    "ArtifactView",
    "ClaimRecorded",
    "ClaimRequest",
    "EventPage",
    "FigureRequest",
    "FigureRun",
    "IngestFailure",
    "IngestedFile",
    "MaterialIngested",
    "PlanStage",
    "ReportRendered",
    "ReportRequest",
    "Result",
    "SourceAddress",
    "SourceView",
    "StageOutcome",
    "StageRequest",
    "StageRun",
    "StageWork",
    "TaskCreated",
    "TaskPlan",
    "TaskState",
    "TaskStep",
    "consume_approval",
    "create_task",
    "describe_abandoned",
    "grant_approval",
    "ingest_material",
    "inspect_source",
    "list_artifacts",
    "list_source_addresses",
    "list_sources",
    "list_tasks",
    "read_artifact",
    "read_events",
    "read_plan",
    "read_steps",
    "read_task_state",
    "reconcile_abandoned",
    "record_claim",
    "render_report",
    "request_approval",
    "resolve_abandoned",
    "run_figure",
    "run_stage",
]
