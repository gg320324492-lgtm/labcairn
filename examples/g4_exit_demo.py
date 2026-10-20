"""G4 exit demonstration — a clean-clone launch, and the three surfaces agreeing.

LC-P1-12's acceptance clause is four sentences, and this walks all four of them
against a workspace that did not exist a moment ago:

* **a clean clone developer launch with working smoke path** — a temporary
  workspace and a temporary database, made by ``labcairn init``, with no
  network call and no credential;
* **Web refresh recovers DB snapshot, no repeated operation** — the service is
  read twice and the two reads are the same task, and the one operation the
  workbench can perform is applied once;
* **request approval cannot be spoofed from another origin** — a request
  carrying a foreign origin is refused with and without a token, and a request
  from the right origin without the token is refused;
* **CLI and UI show identical Task state** — the CLI's ``task status --json``
  and the API's task document are compared field by field, from the same store,
  and the report's bytes are compared by hash: the file the report operation
  wrote against the bytes the API serves.

Every step prints what it did and what it proved. A failure raises rather than
prints a warning, so this exits non-zero if a guard stops working.

**The report is rendered once.** The layer's ``render_report`` renders it into
bytes and writes it as a revision; the CLI's ``artifacts list`` names that file
and its hash, and the API serves the same bytes from
``/artifacts/{id}/content``. That is §1.4.2's decision — one renderer, and
both surfaces serve the same bytes — and it is what makes "CLI and Web produce
the same versioned report" a hash comparison rather than a promise.

**Two steps have no surface to drive them, and the demonstration says so** in
its own output rather than hiding it:

* **no surface ingests material.** The application layer has no ingestion
  operation, so the material is ingested through LC-P1-08's own ingestion path;
* **no surface binds a material to a task.** ``labcairn task create`` binds a
  source *directory* and never a source id, so the task is made through the
  layer's ``create_task`` — the operation ``labcairn task create`` itself calls
  — with the ingested material bound to it.

Run it::

    uv run python examples/g4_exit_demo.py

It uses a temporary database and a temporary workspace, executes no network
call, and needs no credential.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from labcairn.analysis.chart.recipe import ChartRecipe
from labcairn.analysis.chart.render import MatplotlibFigureRenderer
from labcairn.analysis.manifest import read_recipe, selection_payload
from labcairn.analysis.operators import parse_operator_reference
from labcairn.analysis.service import AnalysisRequest, analysis_arguments, run_analysis
from labcairn.api.app import create_app
from labcairn.api.bind import DEFAULT_BIND_HOST, DEFAULT_BIND_PORT, own_origin
from labcairn.api.session import SESSION_DIR_NAME, SESSION_FILE_NAME
from labcairn.application import ApplicationContext, create_task, render_report
from labcairn.application.reports import ReportRequest
from labcairn.cli.workspace import (
    DEFAULT_POLICY_RULES,
    load_policy,
    locate,
    read_config,
    write_config,
    write_policy,
)
from labcairn.core.ids import ApprovalId, OperationId
from labcairn.db import create_db_engine, create_session_factory
from labcairn.db.migrations import head_revision
from labcairn.db.repository import TaskStore
from labcairn.material.ingest import ingest_into_store
from labcairn.recovery.resume import STALE_REASON, MaterialResolver, ResumeCoordinator
from labcairn.reports.receipt import ArtifactStaleness
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import (
    ApprovalGrant,
    ApprovalLedger,
    SourceBinding,
    make_approval,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, Rule
from labcairn.workspace.roots import Workspace

#: The recipe, as a committed document. Read, never written: the figure's
#: editable source is a file a person edits, and a script that generated it
#: would make the recipe a copy of the script instead.
RECIPE_FILE: Path = Path(__file__).resolve().parent / "g4_exit_demo_recipe.json"

#: Where the recipe goes inside the demonstration's workspace. Workspace-
#: relative, because the run path records the recipe by that spelling.
RECIPE_KEY: str = RECIPE_FILE.name

#: The controlled corpus. LC-P1-10's fixture, whose statistics were written
#: down by hand beside it -- not a table invented inside this script.
CORPUS: Path = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "analysis" / "groups.csv"
)

#: The material's name inside the workspace's source root, and the root's
#: own name. Both are the CLI's defaults, so the demonstration is a developer
#: launch rather than a bespoke layout.
MATERIALS_DIR: str = "materials"
MATERIAL_KEY: str = "groups.csv"
MATERIAL_PATH: str = f"{MATERIALS_DIR}/{MATERIAL_KEY}"

#: A fixed moment. Nothing in this file reads the wall clock, so two runs of
#: it differ only in what they measured.
NOW: datetime = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)

#: The operator's rules, on top of the ones ``init`` writes.
#:
#: The default policy denies everything the report path needs -- there is no
#: ``report.render`` in it, and no ``analysis.run`` -- and that is the right
#: posture for a workspace nobody has configured. The demonstration is a
#: developer configuring one, so it writes the rules into the workspace's own
#: policy file, where the operator can see them and change them.
OPERATOR_RULES: tuple[Rule, ...] = (
    *DEFAULT_POLICY_RULES,
    Rule(
        effect=Permission.ALLOW,
        pattern="**",
        capabilities=frozenset(
            {
                "analysis.run",
                "report.render",
                "fs.read",
                "fs.list",
                "fs.write",
            }
        ),
        note="the report path, for the demonstration's own workspace",
    ),
)

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
    print(f"  [ok] {label}" + (f"  - {detail}" if detail else ""))


def rule(title: str) -> None:
    """A step's heading."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def run_cli(workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """The console script, as a developer types it.

    A subprocess, and not the Typer functions in this process: the exit code
    and the bytes on standard output are exactly what a script depends on, and
    a demonstration that called the commands in-process would be testing the
    functions rather than the command line.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set because the child's output
    encoding and terminal width are otherwise the machine's business, and
    neither is a fact about the CLI.
    """
    script = Path(sys.executable).parent / ("labcairn.exe" if os.name == "nt" else "labcairn")
    if not script.is_file():
        raise AssertionError(
            f"FAILED: the console script is not installed at {script}. The "
            "demonstration drives the CLI through the script a developer types, "
            "so it has to be there; run `uv sync`."
        )
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return subprocess.run(
        [str(script), "--workspace", str(workspace), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=300,
    )


def leaves(document: Any, path: str = "") -> dict[str, Any]:
    """Every leaf of a document, by the path that names it.

    A comparison that says *which* field differs is worth more than one that
    says the documents differ, and a comparison that counts the fields it
    looked at is worth more than one that cannot say it looked at anything.
    """
    if isinstance(document, Mapping):
        found: dict[str, Any] = {}
        for key, value in document.items():
            found.update(leaves(value, f"{path}.{key}"))
        return found
    if isinstance(document, list):
        found = {}
        for index, value in enumerate(document):
            found.update(leaves(value, f"{path}[{index}]"))
        return found
    return {path: document}


def digest(data: bytes) -> str:
    """The SHA-256 of some bytes, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def release(*sessions: Session) -> None:
    """Close the transactions the given sessions hold.

    The store's engine opens every transaction with ``BEGIN IMMEDIATE``, so a
    session that has read and not yet committed holds SQLite's write lock. A
    second process is then refused with "database is locked" once the busy
    timeout runs out -- and the service's session lives as long as the service
    does, so **the CLI and the local API cannot be used against one workspace
    at the same time**. The demonstration says so in its own output, and
    closes the transactions between the two surfaces' reads so that both can
    be driven at all.
    """
    for session in sessions:
        session.rollback()


def main() -> int:
    print("LabCairn - G4 exit demonstration (LC-P1-12)")
    print("A clean-clone launch, and the CLI, the API and the workbench's reads agreeing.")
    print("No network, no credential, no model call.\n")

    with tempfile.TemporaryDirectory() as raw:
        return demonstrate(Path(raw) / "workspace")


def demonstrate(root: Path) -> int:
    """The eight steps, in the order the acceptance clause names them.

    The store's handle is opened here and released here, whatever the
    demonstration does: a database file left open on Windows is a temporary
    directory that cannot be removed, and a demonstration that leaves its
    workspace behind is not a clean-clone launch.
    """
    engine = create_db_engine(root / "labcairn.db")
    session = create_session_factory(engine)()
    try:
        return _walk_the_path(root, session)
    finally:
        session.close()
        engine.dispose()


def _walk_the_path(root: Path, session: Session) -> int:
    """The steps themselves."""
    store = TaskStore(session)
    ledger = ApprovalLedger()

    # -- 1. init ------------------------------------------------------------- #
    rule("1. labcairn init - a workspace, a database, a source root, a policy")

    result = run_cli(root, "init", "--json")
    check("the command succeeded", result.returncode == 0, result.stderr.strip()[-300:])
    initialised = json.loads(result.stdout)
    print(f"  workspace  : {initialised['root']}")
    print(f"  database   : {initialised['database_path']}")
    print(f"  schema     : {initialised['migration_revision']}")
    print(f"  sources    : {', '.join(initialised['source_dirs'])}")
    print(f"  policy     : {initialised['policy_digest'][:12]}")
    check(
        "the database is at the newest migration",
        initialised["migration_revision"] == head_revision(),
        f"{initialised['migration_revision']} vs {head_revision()}",
    )
    check(
        "the workspace has the source root the CLI's own default names",
        list(initialised["source_dirs"]) == [MATERIALS_DIR],
        str(initialised["source_dirs"]),
    )
    check(
        "the policy was written where the operator can edit it",
        (root / ".labcairn" / "policy.json").is_file(),
    )

    # -- 2. doctor ----------------------------------------------------------- #
    rule("2. labcairn doctor - what it found")

    result = run_cli(root, "doctor", "--json")
    check("the command succeeded", result.returncode == 0, result.stderr.strip()[-300:])
    findings = json.loads(result.stdout)
    print(f"  workspace  : initialised={findings['workspace']['initialised']}")
    print(
        f"  database   : present={findings['database']['present']} "
        f"at_head={findings['database']['at_head']}"
    )
    print(f"  policy     : {findings['policy']['source']}")
    print(f"  providers  : {len(findings['providers'])} configured")
    print(f"  api session: present={findings['api_session']['present']}")
    check(
        "the workspace is a workspace",
        findings["workspace"]["initialised"] is True,
    )
    check(
        "the database is at the head migration",
        findings["database"]["at_head"] is True,
        f"revision {findings['database']['revision']}",
    )
    check(
        "no model provider is configured, so nothing was asked of one",
        findings["providers"] == [],
    )
    check(
        "no API session exists yet, because the service has not started",
        findings["api_session"]["present"] is False,
    )

    # -- the operator's policy, and the store ------------------------------- #
    location = locate(root)
    default_digest = load_policy(location).digest()
    write_policy(location, OPERATOR_RULES)
    policy = load_policy(location)
    print(f"\n  the default policy {default_digest[:12]} denies every capability the")
    print(f"  report path needs; the operator's policy {policy.digest()[:12]} allows them.")

    # -- 3. the material and the task ---------------------------------------- #
    rule("3. A material, and a task it is bound to")

    materials = root / MATERIALS_DIR
    materials.mkdir(parents=True, exist_ok=True)
    (materials / MATERIAL_KEY).write_bytes(CORPUS.read_bytes())
    (root / RECIPE_KEY).write_bytes(RECIPE_FILE.read_bytes())

    ingested = ingest_into_store(
        session,
        CORPUS.read_bytes(),
        relative_path=MATERIAL_PATH,
        display_name=MATERIAL_KEY,
        ingested_at=NOW,
    )
    source = ingested.material.source
    session.commit()
    print(f"  material   : {MATERIAL_PATH}")
    print(f"  source     : {source.source_id}")
    print(f"  hash       : {source.content_sha256}")
    print(f"  readable   : {source.readability.value}")
    check(
        "the material is in the ledger, and the ledger can read it",
        source.readability.value == "readable",
        source.source_id,
    )

    created = create_task(
        store=store,
        policy=policy,
        workspace_root=root,
        title="G4 exit demonstration",
        goal=TaskGoal(
            objective="One controlled table, one figure, one report.",
            success_criterion=(
                "The CLI, the API and the workbench show the same task, and the "
                "report's bytes are the same bytes."
            ),
        ),
        source_dirs=(materials,),
        bound_source_ids=(source.source_id,),
        now=NOW,
    )
    task_id = created.task.task_id
    session.commit()
    config = read_config(location)
    write_config(location, config.model_copy(update={"current_task": str(task_id)}))
    print(f"  task       : {task_id}")
    print(f"  bound      : {', '.join(created.task.bound_source_ids) or '(nothing)'}")
    check(
        "the task holds the material it was bound to",
        created.task.bound_source_ids == (source.source_id,),
        str(created.task.bound_source_ids),
    )
    print(
        "  note       : `labcairn task create` binds a source *directory* and\n"
        "                never a source id, so the task was made through the\n"
        "                layer's create_task -- the operation that command calls.\n"
        "                tests/test_developer_launch.py records that gap."
    )

    # -- 4. the report ------------------------------------------------------- #
    rule("4. The report - the layer renders it, and records the revision")

    workspace = Workspace.bind(root, task_id=task_id, source_dirs=(materials,))
    root_id = workspace.source_roots[0].root_id
    recipe = ChartRecipe.model_validate_json((root / RECIPE_KEY).read_bytes())
    recipe_ref = read_recipe(root, RECIPE_KEY)
    selection = recipe.data.selection.to_selection(source.source_id, source.content_sha256)
    operator_id, _version = parse_operator_reference(recipe.data.operator)
    arguments = {
        "path": MATERIAL_KEY,
        "operator_id": operator_id,
        "parameters": {**recipe.data.parameters, "selection": selection_payload(selection)},
    }

    approval = make_approval(
        task_id=task_id,
        operation_id=OperationId("00000000-0000-7000-8000-000000000001"),
        capability=CapabilityId.ANALYSIS_RUN.value,
        resource=workspace.path_in(MATERIAL_KEY, root_id),
        args=analysis_arguments(arguments),
        depends_on=(source.content_sha256,),
        expires_at=NOW + timedelta(hours=1),
    )
    granted = approval.model_copy(update={"state": ApprovalState.GRANTED, "granted_at": NOW})
    ledger.issue(
        ApprovalGrant(
            approval=granted,
            policy_digest=policy.digest(),
            sources=(
                SourceBinding(resource_key=MATERIAL_KEY, expected_hash=source.content_sha256),
            ),
        )
    )

    run = run_analysis(
        request=AnalysisRequest(
            approval_id=ApprovalId(granted.approval_id),
            root_id=root_id,
            arguments=arguments,
        ),
        store=store,
        workspace=workspace,
        policy=policy,
        ledger=ledger,
        renderer=MatplotlibFigureRenderer(
            recipe=recipe, recipe_ref=recipe_ref, workspace_root=root
        ),
        recipe=RECIPE_KEY,
        now=NOW,
    )
    session.commit()
    if run.figure_receipt is None:
        raise AssertionError("FAILED: the analysis wrote no figure")
    print(f"  figure     : {run.figure_receipt.relative_path}")
    print(f"  manifest   : {run.manifest_receipt.relative_path}")

    context = ApplicationContext(workspace=workspace, store=store, policy=policy, ledger=ledger)
    rendered = render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=NOW,
    )
    session.commit()
    revision_one = root / "output" / str(task_id) / "report" / "v1"
    print(f"  revision   : v{rendered.receipt.revision}")
    print(f"  document   : {rendered.receipt.relative_path}")
    for form in (
        "report.json",
        "report-manifest.json",
        "report.md",
        "report.html",
        "report.docx",
        "report.pdf",
    ):
        print(f"    {form:<20} {(revision_one / form).stat().st_size:>8} byte(s)")
    check(
        "the revision wrote the canonical document, the manifest and the four forms",
        all(
            (revision_one / form).is_file()
            for form in (
                "report.json",
                "report-manifest.json",
                "report.md",
                "report.html",
                "report.docx",
                "report.pdf",
            )
        ),
    )
    check(
        "the DOCX is a ZIP and the PDF is a PDF",
        (revision_one / "report.docx").read_bytes()[:2] == b"PK"
        and (revision_one / "report.pdf").read_bytes()[:4] == b"%PDF",
    )
    check(
        "the report's revision number is one, because it is the first",
        rendered.receipt.revision == 1,
    )

    # -- the service --------------------------------------------------------- #
    api_engine = create_db_engine(root / "labcairn.db")
    api_session = create_session_factory(api_engine)()
    api_context = ApplicationContext(
        workspace=Workspace.bind(root, task_id=task_id, source_dirs=(materials,)),
        store=TaskStore(api_session),
        policy=policy,
        ledger=ApprovalLedger(),
    )
    app = create_app(api_context, host=DEFAULT_BIND_HOST, port=DEFAULT_BIND_PORT)
    origin = own_origin(DEFAULT_BIND_HOST, DEFAULT_BIND_PORT)
    token = (root / SESSION_DIR_NAME / SESSION_FILE_NAME).read_text(encoding="utf-8").strip()
    print(f"\n  the service's own origin is {origin}, and its session token is in")
    print(f"  {root / SESSION_DIR_NAME / SESSION_FILE_NAME}")

    try:
        with TestClient(app) as client:

            def cli_now(*arguments: str) -> subprocess.CompletedProcess[str]:
                """The console script, with the open transactions closed first.

                See :func:`release`: the store's engine takes SQLite's write
                lock for every transaction, so the service's open session and
                the CLI's own would otherwise refuse each other.
                """
                release(api_session, session)
                return run_cli(root, *arguments)

            # -- 5. the three surfaces agree -------------------------------- #
            rule("5. The three surfaces agree - the CLI, the API, and the workbench's reads")

            result = cli_now("task", "status", "--json")
            check(
                "the CLI's status succeeded", result.returncode == 0, result.stderr.strip()[-300:]
            )
            cli_state = json.loads(result.stdout)
            release(session)
            api_state = client.get("/task", headers={"Origin": origin}).json()
            cli_leaves = leaves(cli_state)
            api_leaves = leaves(api_state)
            differing = sorted(
                name
                for name in set(cli_leaves) | set(api_leaves)
                if cli_leaves.get(name) != api_leaves.get(name)
            )
            check(
                "the CLI's task state and the API's task document are the same, field by field",
                not differing,
                f"{len(cli_leaves)} field(s) compared"
                + (f"; differing: {differing}" if differing else ""),
            )
            print(f"  compared   : {len(cli_leaves)} field(s), {len(differing)} differing")
            print(f"  task       : {cli_state['task']['task_id']}")
            print(f"  bound      : {', '.join(cli_state['task']['bound_source_ids'])}")
            print(f"  artefacts  : {len(cli_state['artifacts'])}")
            print(f"  event seq  : {cli_state['last_event_seq']}")

            result = cli_now("artifacts", "list", "--json")
            check(
                "the CLI's artefact list succeeded",
                result.returncode == 0,
                result.stderr.strip()[-300:],
            )
            listed = json.loads(result.stdout)
            by_name = {
                view["receipt"]["relative_path"].rsplit("/", 1)[-1]: view["receipt"]
                for view in listed
            }
            for form in ("report.md", "report.html", "report.docx", "report.pdf"):
                receipt = by_name.get(form)
                if receipt is None:
                    raise AssertionError(f"FAILED: the CLI does not list {form}")
                on_disk = (root / receipt["relative_path"]).read_bytes()
                served = client.get(
                    f"/artifacts/{receipt['receipt_id']}/content",
                    headers={"Origin": origin},
                )
                check(
                    f"the {form} the CLI names is the bytes the API serves",
                    digest(on_disk) == digest(served.content) == receipt["content_sha256"],
                    f"{receipt['content_sha256'][:12]}",
                )
            print("  (Markdown and HTML are the reproducible forms; the DOCX and the")
            print("   PDF carry container metadata, so their bytes are recorded, not")
            print("   claimed reproducible -- section 1.4.3.)")

            # -- 6. a refresh changes nothing, and repeats nothing ---------- #
            rule("6. A refresh changes nothing, and repeats nothing")

            first = client.get("/task", headers={"Origin": origin}).json()
            second = client.get("/task", headers={"Origin": origin}).json()
            check(
                "the workbench's re-read is the task it read before",
                first == second,
                f"{len(leaves(first))} field(s)",
            )
            result = cli_now("task", "status", "--json")
            check(
                "the CLI's status succeeded", result.returncode == 0, result.stderr.strip()[-300:]
            )
            check(
                "and it is the task in the database",
                json.loads(result.stdout) == second,
                "the CLI's second read and the API's second read agree",
            )

            release(session, api_session)
            body = {
                "capability": CapabilityId.SOURCE_INVENTORY.value,
                "arguments": {},
                "root_id": root_id,
                "resource_key": MATERIAL_KEY,
                "expires_at": (NOW + timedelta(hours=1)).isoformat(),
            }
            authorised = {"Origin": origin, "Authorization": f"Bearer {token}"}
            asked = client.post("/approvals", json=body, headers=authorised)
            check(
                "the workbench's one operation was asked for, and the question was recorded",
                asked.status_code == 201,
                f"status {asked.status_code}",
            )
            approval_id = asked.json()["approval"]["approval_id"]
            release(session, api_session)
            applied = client.post(f"/approvals/{approval_id}/grant", headers=authorised)
            check(
                "the grant was applied",
                applied.status_code == 200,
                f"status {applied.status_code}",
            )
            release(session, api_session)
            repeated = client.post(f"/approvals/{approval_id}/grant", headers=authorised)
            check(
                "the same grant again is refused, so the operation was applied once",
                repeated.status_code == 403 and repeated.json()["reason"] == "approval_refused",
                f"status {repeated.status_code}, reason {repeated.json().get('reason')}",
            )
            release(session, api_session)
            after = client.get("/task", headers={"Origin": origin}).json()
            granted_approvals = [
                approval
                for approval in after["approvals"]
                if approval["approval_id"] == approval_id
            ]
            check(
                "the ledger holds one grant, and it is the one that was applied",
                len(granted_approvals) == 1
                and granted_approvals[0]["state"] == ApprovalState.GRANTED.value,
                str([approval["state"] for approval in granted_approvals]),
            )

            # -- 7. an approval cannot be spoofed --------------------------- #
            rule("7. An approval cannot be spoofed from another origin")

            foreign = {"Origin": "https://elsewhere.example"}
            with_token = {**foreign, "Authorization": f"Bearer {token}"}
            own_without_token = {"Origin": origin}

            refused = client.post("/approvals", json=body, headers=foreign)
            check(
                "a request carrying another origin is refused",
                refused.status_code == 403 and refused.json()["reason"] == "origin_refused",
                f"status {refused.status_code}, reason {refused.json().get('reason')}",
            )
            refused = client.post("/approvals", json=body, headers=with_token)
            check(
                "and it is refused even with a valid token",
                refused.status_code == 403 and refused.json()["reason"] == "origin_refused",
                f"status {refused.status_code}, reason {refused.json().get('reason')}",
            )
            refused = client.get("/task", headers=foreign)
            check(
                "a read from another origin is refused too",
                refused.status_code == 403 and refused.json()["reason"] == "origin_refused",
                f"status {refused.status_code}, reason {refused.json().get('reason')}",
            )
            refused = client.post("/approvals", json=body, headers=own_without_token)
            check(
                "a request from the right origin without the token is refused",
                refused.status_code == 401 and refused.json()["reason"] == "session_required",
                f"status {refused.status_code}, reason {refused.json().get('reason')}",
            )
            check(
                "the right origin with the token is served",
                client.get("/task", headers=own_without_token).status_code == 200,
                "a read needs no token",
            )

        # -- 8. the material changes ------------------------------------------ #
        rule("8. The material changes, and the report says so")

        release(api_session)

        (materials / MATERIAL_KEY).write_bytes(CORPUS.read_bytes() + b"D,17\n")
        measured = MaterialResolver(root).snapshot([MATERIAL_PATH])
        observed = measured[MATERIAL_PATH]
        print(f"  the ledger recorded : {source.content_sha256}")
        print(f"  the file now hashes : {observed}")
        check(
            "the repository's own measurement says the material moved",
            observed != source.content_sha256,
        )

        coordinator = ResumeCoordinator(store, session, workspace_root=root)
        invalidation = coordinator.invalidate_on_source_change(task_id, [source.content_sha256])
        session.commit()
        stale = coordinator.stale_artifacts(task_id)
        stale_ids = {receipt.receipt_id for receipt in stale}
        print(f"  stale artefacts : {len(stale_ids)}")
        check(
            "the repository's own walk marked the report stale",
            rendered.receipt.receipt_id in stale_ids,
            rendered.receipt.receipt_id,
        )
        check(
            "with the repository's own reason, and not one invented here",
            all(
                receipt.staleness is ArtifactStaleness.STALE
                and receipt.staleness_reason == STALE_REASON
                for receipt in stale
            ),
            STALE_REASON,
        )
        check(
            "the walk named the hash it was given, and only that",
            tuple(invalidation.changed_hashes) == (source.content_sha256,),
        )

        before = {path.name: digest(path.read_bytes()) for path in sorted(revision_one.iterdir())}
        second_revision = render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=NOW + timedelta(minutes=1),
        )
        session.commit()
        after = {path.name: digest(path.read_bytes()) for path in sorted(revision_one.iterdir())}
        revision_two = root / "output" / str(task_id) / "report" / "v2"
        check(
            "the re-render is a new revision, with its own files",
            second_revision.receipt.revision == 2 and revision_two.is_dir(),
            f"v{second_revision.receipt.revision}",
        )
        check(
            "and the first revision's bytes are unchanged",
            before == after,
            f"{len(before)} file(s)",
        )
        print(f"  v1 and v2 differ, and v1 is untouched: {sorted(before)}")
    finally:
        api_session.close()
        api_engine.dispose()
        session.close()

    rule("Result")
    print(f"{len(PASSED)} checks passed.")
    print()
    print("What this did not exercise, said plainly:")
    print("  * The React application was not run in a browser. The workbench is")
    print("    driven here through the API it reads -- GET /task, GET /artifacts")
    print("    and GET /artifacts/{id}/content -- and the workbench's own")
    print("    vitest suite covers the application around those reads.")
    print("  * The API's event stream is not consumed by the workbench. That is")
    print("    a decision, not an oversight (web/src/api/paths.ts), and so")
    print("    nothing here demonstrated a client reading it.")
    print("  * The workbench cannot switch the selected project: the API has")
    print("    no such operation, so there was nothing to drive.")
    print("  * The DOCX and the PDF are not byte-reproducible, so their bytes")
    print("    were compared as stored against served, not across two renders.")
    print("  * A report that carries a claim needs an evidence record and the")
    print("    anchors it cites, and nothing in the product writes an anchor,")
    print("    so this report carries a figure rather than a finding.")
    print("  * The CLI and the service were not driven at the same instant. The")
    print("    store's engine opens every transaction with BEGIN IMMEDIATE, so")
    print("    the service's open session holds SQLite's write lock and a CLI")
    print("    command is refused with 'database is locked'. The transactions")
    print("    were closed between the two surfaces' reads so that both could be")
    print("    driven at all; that is a workaround for a limitation in the")
    print("    product, and not a property of the product.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
