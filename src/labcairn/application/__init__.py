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

**Every operation on the task's own state goes through the capability model.**
The capability id, the policy verdict and the approval ledger's ``consume`` —
with the arguments' digest recomputed at the moment of use — are applied in
:mod:`labcairn.application.consent`, once, for every such operation. So a
surface cannot grant itself a permission the other surfaces would not, and
the question "may this happen?" is answered in one place.

**The exceptions are named, not hidden.** Some operations do not ask the
capability model, and the table below says which and why. The reason is
always the same shape: the rows they reach name **no resource of their own**,
so the permission that governs them is the permission on something else, and
it is asked where that something is named. A row that names no path cannot be
judged by a policy about paths. The modules that hold those operations carry
the argument in full: :mod:`labcairn.application.chain`,
:mod:`labcairn.application.guidance` and :mod:`labcairn.application.roles`
say which permission governs them and who asks it.

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
``record_model_proposal``  ``source.inventory``
``attest_claim``          ``source.inventory``
``confirm_proposal``       ``source.inventory``
``list_task_records``       ``fs.read``
``ingest_material``        ``source.inventory``
``list_artifacts``         ``fs.list``
``read_artifact``          ``fs.read``
``request_approval``       the caller's
``grant_approval``         — (it *is* the consent)
``consume_approval``       the approved one
``render_report``          ``report.render``
``run_figure``             ``analysis.run``
``record_project``         ``fs.write``
``record_version``         ``source.inventory``
``record_edge``            ``source.inventory``
``record_confirmation``    ``source.inventory``
``read_project``           ``fs.read``
``read_version``           ``source.inventory``
``read_edge``              ``source.inventory``
``list_versions``          ``source.inventory``
``list_edges``             ``source.inventory``
``list_rejections``        — (the project's own rows)
``describe_abandoned``     — (the task's own operations)
``reconcile_abandoned``    — (the task's own operations)
``resolve_abandoned``      — (the task's own operations)
=========================  ===========================================

**The mentor line's own rows.** The operations below reach rows that belong
to a paper project, to the guidance memory and to the role contracts rather
than to a task. **None of them names a path**, so none of them can be judged
by a policy about paths: the permission that governs them is the permission
on the material, and it is asked where the material is named — the retrieval
asks it per source at serve time and drops the sources the reader may not
reach (ADR-0003 C5). A role contract names no material either, and it holds
its own boundary: the capabilities it lists, and the actions it forbids.

Centralising these reads is what makes a guard added to those modules reach
**every** caller, which is the property the seam exists for.

====================================  ========================================
Operation  The permission that governs it
====================================  ========================================
``read_comments``                     the material's — asked where it is named
``read_edits``                        the material's — asked where it is named
``read_response_states``              the material's — asked where it is named
``read_material_paths``               the material's — asked where it is named
``read_project_graph``                the material's — asked where it is named
``read_guidance_rule``                the material's — asked where it is named
``read_guidance_rules``               the material's — asked where it is named
``write_guidance_rule_version``       the material's — asked where it is named
``write_guidance_rule_confirmation``  the material's — asked where it is named
``write_guidance_rule_resolution``    the material's — asked where it is named
``write_guidance_rule_withdrawal``    the material's — asked where it is named
``write_guidance_counterexample``     the material's — asked where it is named
``read_role_spec``                    the contract's own allowed capabilities
``write_role_spec``                   the contract's own allowed capabilities
====================================  ========================================
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
from labcairn.application.chain import (
    ChainComment,
    ChainEdge,
    ChainEdit,
    ProjectGraph,
    read_comments,
    read_edits,
    read_material_paths,
    read_project_graph,
    read_response_states,
)
from labcairn.application.context import ApplicationContext
from labcairn.application.events import EventPage, read_events
from labcairn.application.evidence import (
    ClaimRecorded,
    ClaimRequest,
    SourceAddress,
    attest_claim,
    confirm_proposal,
    list_source_addresses,
    list_task_records,
    record_claim,
    record_model_proposal,
)
from labcairn.application.guidance import (
    RuleDraft,
    read_guidance_rule,
    read_guidance_rules,
    write_guidance_counterexample,
    write_guidance_rule_confirmation,
    write_guidance_rule_resolution,
    write_guidance_rule_version,
    write_guidance_rule_withdrawal,
)
from labcairn.application.material_ingestion import (
    IngestedFile,
    IngestFailure,
    MaterialIngested,
    ingest_material,
)
from labcairn.application.models import Result
from labcairn.application.papers import (
    ConfirmationRecorded,
    ConfirmationRequest,
    EdgeRequest,
    EdgeStored,
    ProjectRequest,
    ProjectStored,
    VersionRequest,
    VersionStored,
    list_edges,
    list_rejections,
    list_versions,
    read_edge,
    read_project,
    read_version,
    record_confirmation,
    record_edge,
    record_project,
    record_version,
)
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
from labcairn.application.roles import RoleSpecDraft, read_role_spec, write_role_spec
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
    "ChainComment",
    "ChainEdge",
    "ChainEdit",
    "ClaimRecorded",
    "ClaimRequest",
    "ConfirmationRecorded",
    "ConfirmationRequest",
    "EdgeRequest",
    "EdgeStored",
    "EventPage",
    "FigureRequest",
    "FigureRun",
    "IngestFailure",
    "IngestedFile",
    "MaterialIngested",
    "PlanStage",
    "ProjectGraph",
    "ProjectRequest",
    "ProjectStored",
    "ReportRendered",
    "ReportRequest",
    "Result",
    "RoleSpecDraft",
    "RuleDraft",
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
    "VersionRequest",
    "VersionStored",
    "attest_claim",
    "confirm_proposal",
    "consume_approval",
    "create_task",
    "describe_abandoned",
    "grant_approval",
    "ingest_material",
    "inspect_source",
    "list_artifacts",
    "list_edges",
    "list_rejections",
    "list_source_addresses",
    "list_sources",
    "list_task_records",
    "list_tasks",
    "list_versions",
    "read_artifact",
    "read_comments",
    "read_edge",
    "read_edits",
    "read_events",
    "read_guidance_rule",
    "read_guidance_rules",
    "read_material_paths",
    "read_plan",
    "read_project",
    "read_project_graph",
    "read_response_states",
    "read_role_spec",
    "read_steps",
    "read_task_state",
    "read_version",
    "reconcile_abandoned",
    "record_claim",
    "record_confirmation",
    "record_edge",
    "record_model_proposal",
    "record_project",
    "record_version",
    "render_report",
    "request_approval",
    "resolve_abandoned",
    "run_figure",
    "run_stage",
    "write_guidance_counterexample",
    "write_guidance_rule_confirmation",
    "write_guidance_rule_resolution",
    "write_guidance_rule_version",
    "write_guidance_rule_withdrawal",
    "write_role_spec",
]
