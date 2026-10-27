"""LC-P1-10's exit demonstration: a file, a number, a figure, and a record.

LC-P1-10 turns a table into a number, a figure and a manifest, and the work
order's claim is that the three can be checked against each other afterwards.
This is the demonstration of that: one controlled CSV goes in, and what comes
out is a number that names the cells it came from, a figure drawn from a
recipe, a manifest that says how to repeat both, and -- once the input file
has been changed -- a record that says the figure is no longer current.

Six steps, and each is a claim rather than a narration. Every step ends in a
``check()`` that raises rather than warns, so a guard that stopped working
exits non-zero instead of printing a warning nobody reads.

**The consent is not optional.** The demonstration goes through a granted
``analysis.run`` approval, and shows the two refusals that give the consent
its meaning: a run with no approval at all, and a run under an approval that
promised different cells.

**The recipe is the figure's editable source, and it is committed.**
``examples/analysis_demo_recipe.json`` is a document a person edits by hand;
the operator, the selection and the parameters are read out of it rather than
written out again here, so the recipe and the run cannot disagree.

**The data is the corpus.** The CSV is ``tests/fixtures/analysis/groups.csv``
-- the controlled fixture whose statistics were written down by hand beside
it -- rather than a table invented inside this script.

Run it::

    uv run python examples/analysis_demo.py

It uses a temporary database and a temporary workspace, executes no network
call, and needs no credential.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import tempfile
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from labcairn.analysis.chart.recipe import ChartRecipe
from labcairn.analysis.chart.render import MatplotlibFigureRenderer
from labcairn.analysis.manifest import (
    FileRef,
    canonical_digest,
    read_recipe,
    selection_payload,
)
from labcairn.analysis.operators import parse_operator_reference
from labcairn.analysis.operators.grouped import GroupedResult
from labcairn.analysis.selection import RowRange, Selection
from labcairn.analysis.service import (
    AnalysisRefusal,
    AnalysisRefusedError,
    AnalysisRequest,
    analysis_arguments,
    run_analysis,
)
from labcairn.core.ids import ApprovalId, OperationId, RunId, StageId, TaskId, new_id
from labcairn.db.materials import current_texts
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.material.addressing import render_locator_key
from labcairn.material.ingest import ingest_into_store
from labcairn.recovery.resume import STALE_REASON, MaterialResolver, ResumeCoordinator
from labcairn.reports.receipt import ArtifactStaleness
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus, Task, TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import (
    ApprovalGrant,
    ApprovalLedger,
    SourceBinding,
    make_approval,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.locators import CsvLocator
from labcairn.sources.quantity import read_number
from labcairn.workspace.roots import Workspace

#: The recipe, as a committed document. Read, never written: the figure's
#: editable source is a file a person edits, and a script that generated it
#: would make the recipe a copy of the script instead.
RECIPE_FILE: Path = Path(__file__).resolve().parent / "analysis_demo_recipe.json"

#: Where the recipe goes inside the demonstration's workspace. Workspace-
#: relative, because the run path records the recipe by that spelling.
RECIPE_KEY: str = RECIPE_FILE.name

#: The controlled fixture. LC-P1-10's corpus, whose statistics were written
#: down by hand beside it -- not a table invented inside this script.
CORPUS: Path = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "analysis" / "groups.csv"
)

#: A fixed moment. Nothing in this file reads the wall clock, so two runs of
#: it differ only in what they measured.
NOW: datetime = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

#: The checks that passed, in order.
PASSED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Record one claim, and fail loudly when it does not hold.

    A warning would leave the demonstration's exit code saying "fine" while a
    guard had stopped working, and a demonstration nobody can trust is worse
    than no demonstration.
    """
    if not condition:
        raise AssertionError(f"FAILED: {label} {detail}")
    PASSED.append(label)
    print(f"  [ok] {label}" + (f"  — {detail}" if detail else ""))


def rule(title: str) -> None:
    """A step's heading."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def source_location(workspace: Workspace, relative: str) -> tuple[str, str]:
    """The source root the recipe's file is in, and its key within that root.

    The recipe names the file workspace-relative and a resource key is
    root-relative, so the two have to be reconciled once. Doing it here, by
    asking the workspace which source root holds the file, means the run's
    arguments, the approval and the recipe all name the same file rather than
    three spellings that have to be trusted to agree.
    """
    target = (workspace.selected_root / Path(*relative.split("/"))).resolve()
    for root in workspace.source_roots:
        try:
            key = target.relative_to(root.path).as_posix()
        except ValueError:
            continue
        return root.root_id, key
    raise AssertionError(f"FAILED: the recipe's file {relative!r} is in no source root")


def grant(
    ledger: ApprovalLedger,
    policy: PermissionPolicy,
    workspace: Workspace,
    *,
    root_id: str,
    key: str,
    arguments: Mapping[str, Any],
    source_hash: str,
) -> ApprovalId:
    """An approval covering exactly this request, granted.

    Built through the service's own :func:`analysis_arguments`, so the digest
    the approval carries is the one the service will recompute at the moment
    of use. An approval whose digest was written out by hand would be a
    digest nobody checked.
    """
    approval = make_approval(
        task_id=workspace.task_id,
        operation_id=OperationId(new_id()),
        capability=CapabilityId.ANALYSIS_RUN.value,
        resource=workspace.path_in(key, root_id),
        args=analysis_arguments(arguments),
        depends_on=(source_hash,),
        expires_at=NOW + timedelta(hours=1),
    )
    granted = approval.model_copy(update={"state": ApprovalState.GRANTED, "granted_at": NOW})
    ledger.issue(
        ApprovalGrant(
            approval=granted,
            policy_digest=policy.digest(),
            sources=(SourceBinding(resource_key=key, expected_hash=source_hash),),
        )
    )
    return granted.approval_id


def narrower(selection: Selection) -> Selection:
    """The recipe's selection, over one row instead of all of them.

    Built from the recipe's own selection rather than written out again, so
    the refusal below is about *which cells* and not about a second document
    that happens to differ.
    """
    rows = selection.rows
    if not isinstance(rows, RowRange):
        raise AssertionError(
            f"FAILED: the recipe's rows are {type(rows).__name__}, and this "
            "demonstration narrows a range"
        )
    return replace(selection, rows=RowRange(start=rows.start, end=rows.start))


def main() -> int:
    print("LabCairn — LC-P1-10 exit demonstration")
    print("A controlled CSV, a grouped aggregate, a figure, a manifest, and a stale record.")
    print("No network, no credential, no model call.\n")

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        root = tmp / "study"
        (root / "sources").mkdir(parents=True)

        # -- the recipe, read from the committed document ------------------- #
        recipe = ChartRecipe.model_validate_json(RECIPE_FILE.read_bytes())
        relative_source = recipe.data.selection.source
        (root / relative_source).write_bytes(CORPUS.read_bytes())
        (root / RECIPE_KEY).write_bytes(RECIPE_FILE.read_bytes())

        # -- the workspace, the ledger and the task ------------------------- #
        task_id = TaskId(new_id())
        workspace = Workspace.bind(root, task_id=task_id, source_dirs=(root / "sources",))
        root_id, key = source_location(workspace, relative_source)

        db = tmp / "labcairn.db"
        upgrade_to_head(db)
        engine = create_db_engine(db)
        session = create_session_factory(engine)()
        store = TaskStore(session, clock=lambda: NOW)
        store.create_task(
            Task(
                task_id=task_id,
                title="LC-P1-10 exit demonstration",
                goal=TaskGoal(
                    objective="Turn one controlled table into a number, a figure and a record.",
                    success_criterion="The number names its cells; the record survives a change.",
                ),
                created_at=NOW,
                updated_at=NOW,
            )
        )
        run_id = RunId(new_id())
        stage_id = StageId(new_id())
        with store.unit(task_id) as work:
            work.put_run(Run(task_id=task_id, run_id=run_id, status=RunStatus.RUNNING))
            work.put_stage(
                Stage(
                    task_id=task_id,
                    run_id=run_id,
                    stage_id=stage_id,
                    name="analyse",
                    status=StageStatus.ENTERED,
                )
            )

        policy = PermissionPolicy.from_rules(
            [
                Rule(
                    effect=Permission.ALLOW,
                    pattern="**",
                    capabilities=frozenset({"analysis.run"}),
                )
            ]
        )
        ledger = ApprovalLedger()

        try:
            return demonstrate(
                workspace=workspace,
                store=store,
                policy=policy,
                ledger=ledger,
                recipe=recipe,
                root_id=root_id,
                key=key,
                relative_source=relative_source,
                stage_id=stage_id,
            )
        finally:
            session.close()
            engine.dispose()


def demonstrate(
    *,
    workspace: Workspace,
    store: TaskStore,
    policy: PermissionPolicy,
    ledger: ApprovalLedger,
    recipe: ChartRecipe,
    root_id: str,
    key: str,
    relative_source: str,
    stage_id: StageId,
) -> int:
    """The six steps, in the order the task breakdown fixes."""
    # -- 1. the controlled CSV, ingested ------------------------------------ #
    rule("1. The controlled CSV, ingested")

    payload = (workspace.selected_root / relative_source).read_bytes()
    outcome = ingest_into_store(
        store.session,
        payload,
        relative_path=relative_source,
        display_name=Path(relative_source).name,
        ingested_at=NOW,
    )
    source = outcome.material.source
    print(f"  file      : {relative_source}")
    print(f"  source    : {source.source_id}")
    print(f"  hash      : {source.content_sha256}")
    print(f"  readable  : {source.readability.value}")

    selection = recipe.data.selection.to_selection(source.source_id, source.content_sha256)
    cells = _cells_by_address(store.session, source.content_sha256)
    named = [(row, column) for row in _rows_of(selection) for column in selection.columns]
    check(
        "the ledger holds a cell for every cell the selection names",
        all(address in cells for address in named),
        f"{len(named)} cell(s) addressed",
    )

    # -- 2. the consent, and the number it authorises ----------------------- #
    rule("2. The consent, and the number it authorises")

    operator_id, _version = parse_operator_reference(recipe.data.operator)
    parameters = {**recipe.data.parameters, "selection": selection_payload(selection)}
    arguments = {
        "path": key,
        "operator_id": operator_id,
        "recipe": RECIPE_KEY,
        "parameters": parameters,
    }
    print(f"  operator  : {recipe.data.operator}")
    print(f"  selection : {list(selection.columns)} over rows {_row_span(selection)}")
    print(f"  path      : {key} in root {root_id} (the recipe's {relative_source})")

    refused = _refusal(
        store=store,
        ledger=ledger,
        policy=policy,
        workspace=workspace,
        recipe=recipe,
        arguments=arguments,
        root_id=root_id,
    )
    check(
        "a run nobody approved is refused",
        refused is AnalysisRefusal.APPROVAL_MISSING,
        refused.value,
    )

    other = narrower(selection)
    other_arguments = {
        "path": key,
        "operator_id": operator_id,
        "recipe": RECIPE_KEY,
        "parameters": {**recipe.data.parameters, "selection": selection_payload(other)},
    }
    other_approval = grant(
        ledger,
        policy,
        workspace,
        root_id=root_id,
        key=key,
        arguments=other_arguments,
        source_hash=source.content_sha256,
    )
    refused = _refusal(
        store=store,
        ledger=ledger,
        policy=policy,
        workspace=workspace,
        recipe=recipe,
        arguments=arguments,
        root_id=root_id,
        approval_id=other_approval,
    )
    check(
        "an approval for other cells does not authorise these",
        refused is AnalysisRefusal.APPROVAL_REFUSED,
        refused.value,
    )

    approval = grant(
        ledger,
        policy,
        workspace,
        root_id=root_id,
        key=key,
        arguments=arguments,
        source_hash=source.content_sha256,
    )
    recipe_ref = read_recipe(workspace.selected_root, RECIPE_KEY)
    renderer = MatplotlibFigureRenderer(
        recipe=recipe,
        recipe_ref=recipe_ref,
        workspace_root=workspace.selected_root,
    )
    run = run_analysis(
        request=AnalysisRequest(
            approval_id=approval,
            root_id=root_id,
            arguments=arguments,
        ),
        store=store,
        workspace=workspace,
        policy=policy,
        ledger=ledger,
        renderer=renderer,
        now=NOW,
    )
    result = run.result
    if not isinstance(result, GroupedResult):
        raise AssertionError(f"FAILED: the run produced {type(result).__name__}, not a table")
    check("the granted run produced a table of groups", bool(result.groups))

    for group in result.groups:
        print(f"  group {group.key!r}: mean = {group.value}")
        for row in group.rows:
            cell = cells.get((row, result.of))
            locator = render_locator_key(CsvLocator(row=row, column=result.of))
            text = cell.text if cell is not None else "<not recorded>"
            print(f"      {locator}  {text}")

    for group in result.groups:
        quantities = [
            read_number(cells[(row, result.of)].text).value
            for row in group.rows
            if (row, result.of) in cells
        ]
        usable = [value for value in quantities if value is not None]
        check(
            f"group {group.key!r} is the mean of the cells it names",
            group.value == statistics.fmean(usable) and group.n_used == len(usable),
            f"n_used={group.n_used}",
        )

    # -- 3. the figure, drawn from the recipe ------------------------------- #
    rule("3. The figure, drawn from the recipe")

    figure_receipt = run.figure_receipt
    if figure_receipt is None:
        raise AssertionError("FAILED: the run wrote no figure")
    figure_path = workspace.selected_root / figure_receipt.relative_path
    figure_bytes = figure_path.read_bytes()
    print(f"  file      : {figure_receipt.relative_path}")
    print(f"  bytes     : {figure_receipt.size_bytes}")
    print(f"  hash      : {figure_receipt.content_sha256}")
    check(
        "the figure on disk is the bytes the receipt records",
        figure_receipt.size_bytes == len(figure_bytes)
        and figure_receipt.content_sha256 == hashlib.sha256(figure_bytes).hexdigest(),
    )
    check(
        "the figure's chain runs back through the manifest to the file",
        [reference.target_id for reference in figure_receipt.derived_from]
        == [run.manifest_receipt.receipt_id, run.manifest.input_file.relative_path],
    )

    # -- 4. the manifest: six fields, and both hashes ------------------------ #
    rule("4. The manifest: the six fields, and both hashes")

    manifest = run.manifest
    print(f"  input file hash : {manifest.input_file.content_sha256}")
    print(
        "  selection       : "
        f"{json.dumps(manifest.locator.parameters['selection'], sort_keys=True)}"
    )
    print(f"  operator version: {manifest.locator.operator_version}  ({manifest.operator})")
    print(
        "  parameters      : "
        f"{json.dumps(_without(manifest.locator.parameters, 'selection'), sort_keys=True)}"
    )
    print(f"  recipe          : {manifest.recipe.relative_path} @ {manifest.recipe.content_sha256}")
    print(f"  output hash     : {manifest.output_sha256}")
    print("  (the output hash is the operator's result, not the figure: the")
    print("   figure's chain names the manifest, so the manifest cannot hash it)")

    manifest_path = workspace.selected_root / run.manifest_receipt.relative_path
    check(
        "the manifest is a file, and its output hash is its output's",
        manifest_path.is_file() and canonical_digest(manifest.output) == manifest.output_sha256,
        manifest_path.name,
    )
    check(
        "the manifest's input hash is the source's own content hash",
        manifest.input_file.content_sha256 == source.content_sha256,
    )
    check(
        "the manifest names the committed recipe, by the same bytes",
        manifest.recipe.content_sha256 == recipe_ref.content_sha256
        and manifest.recipe.relative_path == RECIPE_KEY,
    )

    # -- 5. the same figure, twice ------------------------------------------ #
    rule("5. The same figure, twice")

    again = _render_again(recipe, recipe_ref, workspace, operator_id, result)
    once_more = _render_again(recipe, recipe_ref, workspace, operator_id, result)
    print(f"  run    : {len(figure_bytes)} byte(s), {figure_receipt.content_sha256}")
    print(f"  render : {len(again)} byte(s), {hashlib.sha256(again).hexdigest()}")
    print(f"  render : {len(once_more)} byte(s), {hashlib.sha256(once_more).hexdigest()}")
    check("two renders of one recipe are byte-identical", again == once_more)
    check("a fresh render is the bytes the run wrote", again == figure_bytes)

    # -- 6. the input file changes ------------------------------------------ #
    rule("6. The input file changes")

    coordinator = ResumeCoordinator(store, store.session, workspace_root=workspace.selected_root)
    checkpoint = coordinator.record_checkpoint(
        workspace.task_id,
        stage_id,
        material_hashes=(source.content_sha256,),
    )
    print(f"  checkpoint: {checkpoint.checkpoint_id} over {list(checkpoint.material_hashes)}")

    target = workspace.selected_root / relative_source
    target.write_bytes(payload + b"A,17\n")
    resolver = MaterialResolver(workspace.selected_root)
    measured = resolver.snapshot([relative_source])
    observed = measured[relative_source]
    print(f"  manifest's input hash  : {manifest.input_file.content_sha256}")
    print(f"  the file now hashes to : {observed}")
    check(
        "the manifest's input hash no longer matches the file",
        observed != manifest.input_file.content_sha256,
    )

    plan = coordinator.plan_resume(workspace.task_id, now=measured)
    check(
        "the repository's own measurement says the material moved",
        plan.must_redo,
        plan.stopped_reason or "",
    )

    report = coordinator.invalidate_on_source_change(
        workspace.task_id, list(checkpoint.material_hashes)
    )
    stale = coordinator.stale_artifacts(workspace.task_id)
    stale_ids = {receipt.receipt_id for receipt in stale}
    print(f"  stale artifacts: {sorted(stale_ids)}")
    check(
        "the figure and the manifest are marked stale, with the repository's reason",
        {run.manifest_receipt.receipt_id, figure_receipt.receipt_id} <= stale_ids
        and set(report.stale_artifact_ids) == stale_ids
        and all(
            receipt.staleness is ArtifactStaleness.STALE
            and receipt.staleness_reason == STALE_REASON
            for receipt in stale
        ),
        f"{len(stale)} artifact(s)",
    )

    fresh = grant(
        ledger,
        policy,
        workspace,
        root_id=root_id,
        key=key,
        arguments=arguments,
        source_hash=source.content_sha256,
    )
    refused = _refusal(
        store=store,
        ledger=ledger,
        policy=policy,
        workspace=workspace,
        recipe=recipe,
        arguments=arguments,
        root_id=root_id,
        approval_id=fresh,
    )
    check(
        "a run over the new bytes is refused, not quietly re-run",
        refused is AnalysisRefusal.SOURCE_DRIFTED,
        refused.value,
    )
    check(
        "the figure on disk is still the bytes that were rendered",
        figure_path.read_bytes() == figure_bytes,
    )

    rule("Result")
    print(f"{len(PASSED)} checks passed.")
    print("The number is the mean of the cells it names; the figure is the")
    print("renderer's drawing of that result; the manifest is what makes both")
    print("repeatable; and a changed input leaves a record that says so")
    print("rather than a figure nobody re-checked.")
    return 0


def _refusal(
    *,
    store: TaskStore,
    ledger: ApprovalLedger,
    policy: PermissionPolicy,
    workspace: Workspace,
    recipe: ChartRecipe,
    arguments: Mapping[str, Any],
    root_id: str,
    approval_id: ApprovalId | None = None,
) -> AnalysisRefusal:
    """The reason a run was refused.

    The refusal is caught rather than propagated, because the point of the
    three refusals in this demonstration is that they happen *and* that they
    name what is wrong.
    """
    recipe_ref = read_recipe(workspace.selected_root, RECIPE_KEY)
    try:
        run_analysis(
            request=AnalysisRequest(
                approval_id=approval_id or ApprovalId(new_id()),
                root_id=root_id,
                arguments=arguments,
            ),
            store=store,
            workspace=workspace,
            policy=policy,
            ledger=ledger,
            renderer=MatplotlibFigureRenderer(
                recipe=recipe,
                recipe_ref=recipe_ref,
                workspace_root=workspace.selected_root,
            ),
            now=NOW,
        )
    except AnalysisRefusedError as refused:
        return refused.reason
    raise AssertionError("FAILED: a run that should have been refused was not")


def _render_again(
    recipe: ChartRecipe,
    recipe_ref: FileRef,
    workspace: Workspace,
    operator_id: str,
    result: GroupedResult,
) -> bytes:
    """One more render of the same recipe and the same result.

    A fresh renderer each time, and the environment prepared before the draw,
    so this is a second draw rather than a second reading of the first.
    """
    renderer = MatplotlibFigureRenderer(
        recipe=recipe,
        recipe_ref=recipe_ref,
        workspace_root=workspace.selected_root,
    )
    renderer.prepare()
    payload = renderer.render(operator_id, result)
    if payload is None:
        raise AssertionError("FAILED: the renderer declined to draw a result it had drawn")
    return payload


def _cells_by_address(session: Any, content_hash: str) -> dict[tuple[int, str], Any]:
    """The ledger's current cells, addressed by (physical row, header text)."""
    return {
        (row.row_number, row.column_name): row
        for row in current_texts(session, source_content_sha256=content_hash)
        if row.row_number is not None and row.column_name is not None
    }


def _rows_of(selection: Selection) -> tuple[int, ...]:
    """The physical rows a selection names."""
    rows = selection.rows
    if isinstance(rows, RowRange):
        return tuple(range(rows.start, rows.end + 1))
    raise AssertionError(f"FAILED: the recipe's rows are {type(rows).__name__}")


def _row_span(selection: Selection) -> str:
    """The rows a selection names, as a span a reader can check."""
    rows = selection.rows
    if isinstance(rows, RowRange):
        return f"{rows.start}..{rows.end}"
    return str(rows)


def _without(parameters: Mapping[str, Any], key: str) -> dict[str, Any]:
    """A mapping without one key."""
    return {name: value for name, value in parameters.items() if name != key}


if __name__ == "__main__":
    raise SystemExit(main())
