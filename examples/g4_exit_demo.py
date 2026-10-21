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

**The material goes in through the CLI.** The application layer has an
ingestion operation, and ``labcairn task create`` calls it: the material under
the workspace's source roots is read through the permission boundary, stored
in the ledger, and bound to the task by the ids the ingestion mints. Nothing
here reaches past the surfaces to put a material in the ledger.

**One thing still has no surface, and the demonstration says so** in its own
output rather than hiding it: the product has no operation that writes an
evidence record or an anchor, so the demonstration writes the claim's own
address itself.

**Every comparison is shown a difference it must find.** A comparison that
compares nothing also reports "no differences", so each one is run once over
something that must answer the other way -- a copy of the document with a
difference planted in it, a receipt with another reason, a refusal for another
reason -- and the demonstration insists the comparison finds it. A check that
cannot fail is not a check.

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
import uuid
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
from labcairn.application import ApplicationContext, render_report
from labcairn.application.reports import ReportRequest
from labcairn.cli.workspace import (
    DEFAULT_POLICY_RULES,
    load_policy,
    locate,
    write_policy,
)
from labcairn.core.ids import ApprovalId, OperationId, TaskId
from labcairn.db import create_db_engine, create_session_factory
from labcairn.db.migrations import head_revision
from labcairn.db.models import SourceAnchorRow
from labcairn.db.repository import TaskStore
from labcairn.evidence.cite_support import LocationResolution
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import EvidenceCreator, EvidenceKind, VerificationStatus
from labcairn.evidence.store import append_record
from labcairn.material.addressing import render_locator_key
from labcairn.recovery.resume import STALE_REASON, MaterialResolver, ResumeCoordinator
from labcairn.reports.receipt import ArtifactReceipt, ArtifactStaleness
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import (
    ApprovalGrant,
    ApprovalLedger,
    SourceBinding,
    make_approval,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, Rule
from labcairn.sources.locators import CsvLocator
from labcairn.sources.source import AnchorKind, Source, SourceAnchor, SourceReadability
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

#: The claim the report carries, and the address it rests on.
#:
#: The first data row of the corpus, which the ledger holds as the cell at
#: row 2, column "value" -- the row number counts the header, and the column
#: is the header's own text. The claim is the number **at that address**, so
#: it is true by construction and checkable by anyone who opens the file.
ANCHOR_ID: str = "anc-1"
RECORD_ID: str = "ev-1"
CLAIM_ROW: int = 2
CLAIM_COLUMN: str = "value"
CLAIM_TEXT: str = "1"

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


def the_differences(left: Any, right: Any) -> tuple[str, ...]:
    """The fields two documents differ in, by the path that names them.

    The comparison itself, and nothing else: the demonstration calls it over
    the two surfaces' documents, and calls it again over a copy with a
    difference planted in it, so that a comparison which compares nothing
    cannot pass by saying "no differences".
    """
    left_leaves = leaves(left)
    right_leaves = leaves(right)
    return tuple(
        sorted(
            name
            for name in set(left_leaves) | set(right_leaves)
            if left_leaves.get(name) != right_leaves.get(name)
        )
    )


def the_same_bytes(on_disk: bytes, served: bytes, receipt_hash: str) -> bool:
    """Whether the file on disk, the bytes served and the receipt's hash agree.

    All three, not two of them: the file the report operation wrote and the
    bytes the API serves are the same bytes, and the receipt's hash is what
    the ledger recorded about them.
    """
    return digest(on_disk) == digest(served) == receipt_hash


def is_stale(receipt: ArtifactReceipt) -> bool:
    """Whether the walk marked this receipt stale, with the repository's own reason.

    Both halves: the state, and the reason the repository's own constant
    gives for it. A check that compares only the state would pass on a reason
    somebody else invented.
    """
    return receipt.staleness is ArtifactStaleness.STALE and receipt.staleness_reason == STALE_REASON


def is_refused(response: Any) -> bool:
    """Whether the service refused the request, and said which refusal it was.

    The status and the reason: a 403 with another reason is a different
    refusal, and one the operator would act on differently.
    """
    return response.status_code == 403 and response.json()["reason"] == "approval_refused"


def changed_only(invalidation: Any, expected: str) -> bool:
    """Whether the walk named exactly the hash it was given, and no other."""
    return tuple(invalidation.changed_hashes) == (expected,)


def resolves(session: Session, anchor: SourceAnchor) -> bool:
    """Whether the ledger's index can resolve the anchor's address.

    The report's links check resolves it too; this says so before the report
    is written, so that a failure names the address rather than the report.
    """
    located = LabCairnIndex(session.connection()).locate(anchor)
    return located is not None and located.resolution is LocationResolution.RESOLVED


def release(*sessions: Session) -> None:
    """Close the transactions the given sessions hold.

    The store's engine opens every transaction with ``BEGIN IMMEDIATE``, so a
    session that has read and not yet committed holds SQLite's write lock, and
    a second writer is then refused with "database is locked" once the busy
    timeout runs out.

    **This is the demonstration's own housekeeping, not a limit of the
    product.** A request owns its session and closes it when it is over, so
    the service never holds the store's write lock between requests: the CLI
    and the local API are used against one workspace at the same time, and
    the demonstration says so in its own output. What is left is the
    demonstration's own session, which is read from between the surfaces'
    calls; it is closed here so that the other writer is not refused.
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

    # The material goes into the ledger through the CLI, and the task is bound
    # to it by the same command: the ingestion is the application layer's
    # operation and the CLI is the surface that calls it. Nothing here reaches
    # past the surfaces to put a material in the ledger.
    release(session)
    created = run_cli(
        root,
        "task",
        "create",
        "--title",
        "G4 exit demonstration",
        "--objective",
        "One controlled table, one figure, one report.",
        "--criterion",
        (
            "The CLI, the API and the workbench show the same task, and the "
            "report's bytes are the same bytes."
        ),
        "--source-dir",
        MATERIALS_DIR,
        "--json",
    )
    check("the command succeeded", created.returncode == 0, created.stderr.strip()[-300:])
    task = json.loads(created.stdout)
    task_id = TaskId(uuid.UUID(task["task_id"]))
    bound = tuple(task["bound_source_ids"])
    print(f"  material   : {MATERIAL_PATH}")
    print(f"  task       : {task_id}")
    print(f"  bound      : {', '.join(bound) or '(nothing)'}")
    check(
        "the task holds the material the CLI was told about",
        bool(bound),
        str(bound),
    )

    # And the ledger's own account of it, read back through the CLI: a
    # material that cannot be inspected is a material the ledger cannot serve.
    release(session)
    inspected = run_cli(root, "sources", "inspect", "--source", bound[0], "--json")
    check(
        "the CLI can report the material it ingested",
        inspected.returncode == 0,
        inspected.stderr.strip()[-300:],
    )
    source = Source.model_validate(json.loads(inspected.stdout)["source"])
    print(f"  source     : {source.source_id}")
    print(f"  hash       : {source.content_sha256}")
    print(f"  readable   : {source.readability.value}")
    check(
        "the material is in the ledger, and the ledger can read it",
        source.readability is SourceReadability.READABLE,
        source.source_id,
    )

    # -- 4. the report ------------------------------------------------------- #
    rule("4. The report - the layer renders it, and records the revision")

    # The claim the report will carry, and the address it rests on.
    #
    # A claim rests on a cited record, and a citation points into material the
    # task holds -- which it now does, because the CLI ingested it. **The
    # product has no operation that writes a record or an anchor**, so the
    # demonstration writes the claim's own address itself; that gap is named
    # in the demonstration's own list of what it did not exercise.
    anchor = SourceAnchor(
        anchor_id=ANCHOR_ID,
        source_id=source.source_id,
        kind=AnchorKind.NUMERIC,
        locator=CsvLocator(row=CLAIM_ROW, column=CLAIM_COLUMN),
        bound_source_sha256=source.content_sha256,
        excerpt_sha256=digest(CLAIM_TEXT.encode("utf-8")),
        created_at=NOW,
    )
    session.add(
        SourceAnchorRow(
            anchor_id=anchor.anchor_id,
            source_id=anchor.source_id,
            kind=anchor.kind.value,
            locator_key=render_locator_key(anchor.locator),
            bound_source_sha256=anchor.bound_source_sha256,
            excerpt_sha256=anchor.excerpt_sha256,
            created_at=anchor.created_at,
        )
    )
    record = EvidenceRecord(
        evidence_id=RECORD_ID,
        task_id=str(task_id),
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=float(CLAIM_TEXT),
        unit="dimensionless",
        anchor_ids=(anchor.anchor_id,),
        extracted_span=CLAIM_TEXT,
        extracted_span_sha256=digest(CLAIM_TEXT.encode("utf-8")),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="g4-exit-demonstration",
        source_content_hash=source.content_sha256,
        created_at=NOW,
    )
    append_record(session.connection(), record)
    session.commit()
    print(
        f"  claim      : {record.extracted_span} {record.unit}, at {MATERIAL_PATH} "
        f"row {CLAIM_ROW} column {CLAIM_COLUMN}"
    )
    check(
        "the claim is bound to an address the material answers",
        resolves(session, anchor),
        anchor.anchor_id,
    )

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
    print(f"  chain      : {len(rendered.receipt.derived_from)} link(s)")
    for link in rendered.receipt.derived_from:
        print(f"    {link.target_kind.value:<16} {link.target_id} {link.content_sha256 or ''}")
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
    document = json.loads((revision_one / "report.json").read_text(encoding="utf-8"))
    claims = document["claims"]
    print(f"  claims     : {len(claims)}")
    check(
        "the report carries the claim, and cites the address it rests on",
        len(claims) == 1
        and claims[0]["record"]["anchor_ids"] == [ANCHOR_ID]
        and claims[0]["record"]["value"] == float(CLAIM_TEXT)
        and claims[0]["record"]["unit"] == record.unit,
        f"{len(claims)} claim(s), citing {claims[0]['record']['anchor_ids'] if claims else []}",
    )

    # The control: while the material is unchanged, the repository's own walk
    # says nothing is stale. A walk that always answered "stale" would pass
    # the check in step 8, and the demonstration cannot read its own
    # conclusion back.
    fresh_stale = ResumeCoordinator(store, session, workspace_root=root).stale_artifacts(task_id)
    check(
        "the staleness walk says nothing is stale while the material is unchanged",
        not fresh_stale and rendered.receipt.staleness is not ArtifactStaleness.STALE,
        f"{len(fresh_stale)} stale receipt(s)",
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
                """The console script, with the demonstration's own transaction closed.

                See :func:`release`: the store's engine takes SQLite's write
                lock for every transaction, so the demonstration's own session
                would otherwise refuse the CLI's writer. The service does not:
                a request owns its session and closes it when it is over.
                """
                release(session)
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
            differing = the_differences(cli_state, api_state)
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

            # The two surfaces, one workspace, one moment. The CLI's command
            # above ran while the service below was serving, and the service
            # did not refuse the CLI's writer for it: a request owns its
            # session and closes it when it is over, so the service holds the
            # store's write lock for no one between requests.
            check(
                "the CLI and the service were used against one workspace at the same time",
                result.returncode == 0
                and api_state["task"]["task_id"] == cli_state["task"]["task_id"],
                "the CLI's command succeeded while the service was serving, and both "
                "named the same task",
            )
            print(
                "  one workspace: the CLI and the service drove it together, the "
                "service's session belongs to its requests"
            )

            # The control: the same comparison, over a copy of the API's
            # document with a difference planted in it. A comparison that
            # compares nothing also reports "no differences", so the
            # demonstration insists this one finds what was planted -- and the
            # test that runs this demonstration reads that line.
            planted_state = json.loads(json.dumps(api_state))
            planted_state["task"]["title"] = planted_state["task"]["title"] + " (planted)"
            planted = the_differences(cli_state, planted_state)
            check(
                "the field-by-field comparison finds the difference it was given",
                len(planted) == 1,
                f"{len(planted)} field(s) differ in the altered copy: {planted}",
            )
            print(f"  control    : {len(planted)} field(s) differ in the altered copy")

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
                    the_same_bytes(on_disk, served.content, receipt["content_sha256"]),
                    f"{receipt['content_sha256'][:12]}",
                )
                # The control: the file on disk is not the bytes the service
                # serves, and the comparison has to say so. A comparison that
                # dropped the file on disk from it would say they agree.
                if form == "report.md":
                    check(
                        "the byte comparison finds the difference it was given",
                        not the_same_bytes(
                            on_disk + b" (altered)", served.content, receipt["content_sha256"]
                        ),
                        "the altered file on disk is not the bytes served",
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

            release(session)
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
            release(session)
            applied = client.post(f"/approvals/{approval_id}/grant", headers=authorised)
            check(
                "the grant was applied",
                applied.status_code == 200,
                f"status {applied.status_code}",
            )
            release(session)
            repeated = client.post(f"/approvals/{approval_id}/grant", headers=authorised)
            check(
                "the same grant again is refused, so the operation was applied once",
                is_refused(repeated),
                f"status {repeated.status_code}, reason {repeated.json().get('reason')}",
            )
            # The requirement, stated over the two requests rather than about
            # one of them: the service refused one of them, and it was the
            # second. Stated this way, a check that no longer required the
            # repeated grant to be refused -- and so counted the first one as
            # a refusal too -- would show up as a different list.
            refused_grants = [
                name
                for name, response in (("applied", applied), ("repeated", repeated))
                if is_refused(response)
            ]
            check(
                "of the two grant requests, the service refused the second and accepted the first",
                refused_grants == ["repeated"],
                f"the service refused: {refused_grants}",
            )
            # The control: the same comparison, over the response the service
            # gave when the grant was applied. A check that requires the
            # refusal must be able to say "this one was not refused", or it
            # cannot tell a refusal from an acceptance.
            check(
                "the refusal comparison finds the difference it was given",
                not is_refused(applied),
                f"status {applied.status_code}, reason {applied.json().get('reason')}",
            )
            release(session)
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
            # The control: the refusal comparison, asked about a refusal for
            # another reason, must say "not this one". A comparison that
            # answered "refused" for every 403 could not tell the approval's
            # refusal from this one, and the operator would act on the two
            # differently.
            check(
                "the refusal comparison tells this refusal from another",
                not is_refused(refused),
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

        release(session)

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
        for receipt in stale:
            print(f"    stale  {receipt.receipt_id}")
        print(f"  report receipt  : {rendered.receipt.receipt_id}")
        # The walk's answer is the property, and not "the report": the walk
        # marks the artefacts whose own chain names the material that moved,
        # and what a report's chain names depends on what the report was built
        # from -- a figure, a table, or a claim. So the demonstration asks
        # which of them name the material, and requires the walk to have
        # marked them. The report's own place among them is printed above,
        # and the test that witnesses this demonstration reads it there.
        naming = [
            receipt
            for receipt in stale
            if any(link.content_sha256 == source.content_sha256 for link in receipt.derived_from)
        ]
        check(
            "the repository's own walk marked the artefacts whose chain names the material",
            bool(naming),
            f"{len(naming)} of {len(stale_ids)} stale receipt(s) name the material",
        )
        check(
            "with the repository's own reason, and not one invented here",
            all(is_stale(receipt) for receipt in stale),
            STALE_REASON,
        )
        check(
            "the walk named the hash it was given, and only that",
            changed_only(invalidation, source.content_sha256),
        )
        # The controls: each of these comparisons has to be able to say "no".
        # A comparison that always answered "yes" would pass the checks
        # above, so the demonstration asks each of them about something that
        # must answer the other way.
        #
        # The staleness comparison is asked about a receipt the walk really
        # did mark stale, given another reason: a receipt the walk never
        # marked would answer "no" whatever the comparison compared, and so
        # would be no control at all.
        walked = stale[0]
        check(
            "the staleness comparison finds the difference it was given",
            not is_stale(walked.model_copy(update={"staleness_reason": "another reason"})),
            "a receipt the walk marked stale, but for another reason, is not stale "
            "by the repository's rule",
        )
        check(
            "the changed-hash comparison finds the difference it was given",
            not changed_only(invalidation, "0" * 64),
            "the walk did not name this hash",
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
        # The control: the walk's answer is the walk's own. The revision
        # rendered *after* the material changed is not stale, because the walk
        # marks the artefacts whose chain names the hash that moved -- and a
        # conclusion that said "the material moved, so everything is stale"
        # would say otherwise.
        after_the_change = coordinator.stale_artifacts(task_id)
        after_ids = {receipt.receipt_id for receipt in after_the_change}
        check(
            "the staleness walk says the revision rendered after the change is not stale",
            second_revision.receipt.receipt_id not in after_ids,
            f"{len(after_ids)} stale receipt(s), and v2 is not among them",
        )
        # And the comparison, asked about that same revision: a receipt the
        # walk did not mark stale is not stale by the repository's rule either,
        # so the rule has a state as well as a reason.
        check(
            "the staleness comparison says no about a receipt the walk did not mark",
            not is_stale(second_revision.receipt),
            "the revision rendered after the change is current",
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
    print("  * The product has no operation that writes an evidence record or an")
    print("    anchor, so the demonstration wrote the claim's own address and the")
    print("    record that rests on it itself. The report carries a real claim,")
    print("    cited to a cell of the material the CLI ingested -- but the claim")
    print("    was made by the demonstration, not by the product.")
    print("  * The demonstration's own controls are not exhaustive. Each")
    print("    comparison is run once over something that must answer the other")
    print("    way, which shows that the comparison can fail -- but a check")
    print("    whose own requirement was narrowed would still print its line,")
    print("    and no control would notice. The control asks the comparison a")
    print("    question, and a narrowed requirement is a question the comparison")
    print("    was never asked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
