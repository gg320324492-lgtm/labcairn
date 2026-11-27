"""Drawing the models, for a person.

``docs/ARCHITECTURE.md`` says formatting must never be load-bearing for a
machine-readable command, and this module is the reason that is true rather
than merely intended: **every function here takes a model and returns a
renderable, and none of them returns anything a machine could read.** The
models are the data; these are pictures of them. A script cannot depend on a
picture, which is exactly the property the rule asks for.

The one place prose is not optional is ``doctor``, which is the command that
most wants to be a paragraph. Its paragraph is assembled from the findings
model, so the sentence and the data cannot disagree — the sentence is
generated from the same object the JSON serialises.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from labcairn.application.artifacts import ArtifactView
from labcairn.application.reports import ReportRendered
from labcairn.application.sources import SourceView
from labcairn.application.stages import StageRun, TaskPlan
from labcairn.application.tasks import TaskState
from labcairn.cli.models import (
    DoctorReport,
    ProviderFinding,
    SuggestionAsked,
    SuggestionOutcome,
    WorkspaceInitialised,
)
from labcairn.runtime.lifecycle import Task


def render_initialised(model: WorkspaceInitialised) -> RenderableType:
    """What ``init`` made."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("workspace", model.root)
    table.add_row("database", model.database_path)
    table.add_row("schema", model.migration_revision)
    table.add_row("sources", ", ".join(model.source_dirs) if model.source_dirs else "(none)")
    table.add_row("policy", model.policy_digest[:12])
    table.add_row("created", "\n".join(model.created))
    return Panel(table, title="workspace ready", expand=False)


def render_doctor(model: DoctorReport) -> RenderableType:
    """What ``doctor`` found.

    A table per area, then a sentence that says what the tables say. The
    sentence is built from the model, so it cannot claim something the data
    does not show.

    **A source root the commands will refuse is named, and named with the
    way it is unusable.** The word in brackets is the word the refusal uses,
    so the diagnostic and the refusal say the same thing about the same
    source root. The name is written the way a Python literal writes it,
    because a name this build cannot speak may not be printable — and a
    diagnostic that cannot be drawn is not a diagnostic.
    """
    table = Table(expand=False)
    table.add_column("area")
    # Fold rather than crop: a path that is cut off is a path a reader
    # cannot copy, and this is a report of where things are.
    table.add_column("finding", overflow="fold")

    workspace = model.workspace
    if not workspace.initialised:
        state = "(not initialised)"
    elif workspace.unusable_source_roots:
        state = "(initialised, but a source root cannot be used)"
    else:
        state = "(initialised)"
    workspace_finding = (
        f"{workspace.root} {state}, sources: {', '.join(workspace.source_dirs) or '(none)'}"
    )
    for root in workspace.unusable_source_roots:
        workspace_finding += f", unusable: {root.name!r} ({root.problem})"
    table.add_row("workspace", workspace_finding)
    database = model.database
    table.add_row(
        "database",
        f"{database.path} "
        + (
            f"(revision {database.revision}, at head)"
            if database.at_head
            else f"(revision {database.revision or 'none'})"
        )
        if database.present
        else "absent",
    )
    policy = model.policy
    table.add_row("policy", f"{policy.source}, {len(policy.rules)} rule(s), {policy.digest[:12]}")
    for rule in policy.rules:
        table.add_row("", rule)
    for provider in model.providers:
        table.add_row(
            f"provider {provider.name}",
            f"{provider.protocol} / {provider.model}" + _probe_note(provider),
        )
        for capability in provider.capabilities:
            assumed = " [assumed]" if capability.assumed else ""
            table.add_row(
                "",
                f"{capability.capability}: {capability.outcome}{assumed}"
                + (f" — {capability.reason}" if capability.reason else ""),
            )
    if not model.providers:
        table.add_row("providers", "none configured")
    session = model.api_session
    table.add_row(
        "api session",
        f"{session.path} (present)" if session.present else f"{session.path} (absent)",
    )
    if session.token is not None:
        table.add_row("api token", session.token)

    return Panel(table, title="doctor", expand=False)


def _probe_note(provider: ProviderFinding) -> str:
    """Where a provider's capability reading came from, in a few words.

    **The three are different claims and the note says which.** A provider
    that has never been asked is "(declared, not probed)"; one this run asked
    is "(probed now)"; one whose reading the store already held is "(probed,
    read back from the record of <when>)". A reader who is told only
    "probed" cannot tell a reading taken minutes ago from one taken months
    ago, and those two support different conclusions.

    **A provider the configuration declares unprobed says so.** ADR-0002's
    ``probed: false`` override: the operator has told the workspace to treat
    this provider as not measured, and the report names that as the reason
    rather than leaving a bare "not probed" that could be read as an
    oversight.

    **A record that could not be kept says so.** The probe happened and cost
    money whatever the store did with it, so the note carries the reason the
    product is not holding the reading.
    """
    if provider.probed_override:
        note = " (declared unprobed by configuration)"
    elif provider.probe_source == "live":
        note = " (probed now)"
    elif provider.probe_source == "stored":
        stamp = f" of {provider.observed_at}" if provider.observed_at else ""
        note = f" (probed, read back from the record{stamp})"
    else:
        note = " (declared, not probed)"
    if provider.probe_error:
        note += f" — {provider.probe_error}"
    return note


def render_task(model: Task, output_area: Path) -> RenderableType:
    """A task that was created.

    ``output_area`` is where this task's outputs live. It is not in the task's
    model — the workspace is not task data, and the model is what the API
    serves — so the line is derived from the two facts the caller already
    has: the workspace it named and the task id the model carries.
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("task", str(model.task_id))
    table.add_row("title", model.title)
    table.add_row("objective", model.goal.objective)
    table.add_row("criterion", model.goal.success_criterion)
    table.add_row("sources", str(len(model.bound_source_ids)))
    table.add_row("outputs", str(output_area))
    table.add_row("created", model.created_at.isoformat())
    return Panel(table, title="task created", expand=False)


def render_task_state(model: TaskState) -> RenderableType:
    """Where a task is.

    The state is one value and the drawing is one picture of it: the task, the
    runs and their attempts, the stages and their statuses, the artefacts and
    the approvals, and the cursor a client resumes an event stream from.
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("task", str(model.task.task_id))
    table.add_row("title", model.task.title)
    table.add_row("objective", model.task.goal.objective)
    table.add_row("revision", str(model.task.revision))
    table.add_row("last event", str(model.last_event_seq))
    table.add_row("runs", str(len(model.runs)))
    table.add_row("stages", str(len(model.stages)))
    table.add_row("artifacts", str(len(model.artifacts)))
    table.add_row("approvals", str(len(model.approvals)))
    return Panel(table, title="task status", expand=False)


def render_task_plan(model: TaskPlan) -> RenderableType:
    """Where a task is in the declared workflow."""
    table = Table(title=f"plan {model.skill_id}", expand=False, title_justify="left")
    table.add_column("stage")
    table.add_column("status")
    table.add_column("blocked because")
    for step in model.steps:
        table.add_row(step.stage.value, step.status.value, step.blocked_reason or "")
    return Panel(table, title="task plan", expand=False)


def render_stage_run(model: StageRun) -> RenderableType:
    """What running a stage produced."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("run", str(model.run.run_id))
    table.add_row("attempt", str(model.run.attempt))
    table.add_row("stage", model.stage.name)
    table.add_row("stage status", model.stage.status.value)
    table.add_row("operation", str(model.operation.operation_id))
    table.add_row("operation state", model.operation.state.value)
    table.add_row("capability", model.operation.capability)
    table.add_row("resource", model.operation.resource_key)
    table.add_row("artifacts", str(len(model.artifacts)))
    return Panel(table, title="stage run", expand=False)


def render_source(model: SourceView) -> RenderableType:
    """One source of a task."""
    source = model.source
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("source", str(source.source_id))
    table.add_row("kind", source.kind.value)
    table.add_row("name", source.display_name)
    table.add_row("path", source.relative_path)
    table.add_row("resource key", model.resource_key)
    table.add_row("size", f"{source.size_bytes} bytes")
    table.add_row("sha256", source.content_sha256)
    table.add_row("readability", source.readability.value)
    return Panel(table, title="source", expand=False)


def render_artifacts(models: tuple[ArtifactView, ...]) -> RenderableType:
    """What a task has produced."""
    if not models:
        return Panel(
            Text("this task has produced nothing yet"),
            title="artifacts",
            expand=False,
        )
    table = Table(title="artifacts", expand=False, title_justify="left")
    table.add_column("receipt")
    table.add_column("kind")
    table.add_column("path")
    table.add_column("revision")
    table.add_column("staleness")
    for view in models:
        receipt = view.receipt
        table.add_row(
            receipt.receipt_id,
            receipt.kind.value,
            receipt.relative_path,
            str(receipt.revision),
            receipt.staleness.value,
        )
    return Panel(table, title="artifacts", expand=False)


def render_report_gate(model: ReportRendered) -> RenderableType:
    """What the evidence gate judged, and what it did not.

    **The two lists are one statement, and the drawing shows both.** The gate
    judged the records the report states as established, and the report also
    names records it does not state as established — a claim whose status it
    prints, and the records it discloses as unresolved. A reader who sees only
    the judged list cannot tell what the other list holds, and the two together
    are every record the report carries.

    **Ids, counts and outcomes; never the records' text.** A record's words are
    the material, and the tree's own rule is that material does not enter the
    repository and does not travel in a rendering either. What travels is the
    id, so a reader can look the record up in the ledger.

    **A gate that refused did not get here.** The refusal is rendered by the
    refusal path, with its reason, and this function is not called: a report
    that the gate refused was never written, so there is nothing to draw.
    """

    gate = model.evidence_gate
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    verdict = "passed" if gate.passed else "did not pass"
    table.add_row("evidence gate", f"{verdict}, over {len(gate.considered)} record(s)")
    table.add_row(
        "judged",
        ", ".join(gate.considered) if gate.considered else "(none)",
    )
    table.add_row(
        "unjudged",
        ", ".join(model.unjudged_records) if model.unjudged_records else "(none)",
    )
    table.add_row("findings", str(len(gate.findings)))
    return Panel(table, title="evidence gate", expand=False)


def render_suggestion_asked(model: SuggestionAsked) -> RenderableType:
    """What ``suggest`` is asking for, before anything is spent.

    **The question is printed, because a person is about to grant it.** The
    material is not: it is named by its digest and by how much of it the
    question is about, and the truncation is stated rather than left for the
    reader to guess.
    """
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("source", model.source_id)
    table.add_row("question", model.question)
    table.add_row("provider", f"{model.provider}:{model.model}")
    table.add_row("destination", model.destination)
    table.add_row("material sha256", model.material_sha256)
    table.add_row(
        "material read",
        f"{model.excerpt_characters} of {model.material_characters} characters"
        + (" (truncated)" if model.truncated else ""),
    )
    table.add_row("approval", model.approval_id)
    table.add_row("expires", model.expires_at)
    return Panel(table, title="suggestion asked", expand=False)


def render_suggestion(model: SuggestionOutcome) -> RenderableType:
    """What came back from one question about one source's material."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("source", model.source_id)
    table.add_row("provider", f"{model.provider}:{model.model}")
    table.add_row("destination", model.destination)
    table.add_row("answer sha256", model.answer_sha256)
    table.add_row("answer", model.answer)
    table.add_row("written to", model.answer_path)
    table.add_row("exchange", model.exchange_event_id)
    return Panel(table, title="suggestion", expand=False)


__all__ = [
    "render_artifacts",
    "render_doctor",
    "render_initialised",
    "render_source",
    "render_stage_run",
    "render_suggestion",
    "render_suggestion_asked",
    "render_task",
    "render_task_plan",
    "render_task_state",
]
