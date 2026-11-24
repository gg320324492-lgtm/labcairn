"""The trajectory index's two surfaces: the API route and the CLI's ingest.

**What is under test.** Phase 4 (P4-MS), execution plan §8.1-§8.2, first
source, at its two surfaces. The application layer's
``ingest_paper_trajectory`` already has its own witnesses in
``tests/test_trajectory_index.py``; this file watches the *wiring*:

=================================  =======================================
acceptance                         witness
=================================  =======================================
the API indexes a project          ``POST /trajectory/ingest`` answers with
and serves a search over it        the layer's own counts, and a search
                                   over the indexed comment finds it
an unknown project is refused      the route answers the layer's own
                                   ``chain_project_not_found``, not a crash
a malformed body is refused        a body without ``project_id`` is a 422,
                                   and a blank id is a 422, from the
                                   contract's own field rule
the route changes something, so    a request without the session token is
the session guard covers it        401, and a foreign origin is 403
the CLI indexes what it ingests    ``sources ingest`` over a real chain
                                   reports each paper project's counts
a refused project is reported,     a project the store does not hold is
not swallowed                      an outcome with a refusal, and the
                                   command still exits 0 with the rest of
                                   the report — the same rule an unreadable
                                   file follows
=================================  =======================================

**The fixture is the chain's own.** The comments, versions and edges are
written the way ``feedback_chain_fixtures.build_chain`` writes them — the
same scaffolding the chain's and the index's own witnesses use — so a hit
this file asserts is a hit the product wrote, read back through the surface
under test.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from docx_fixtures import Fixture, write_fixture
from fastapi.testclient import TestClient
from feedback_chain_fixtures import MOMENT, ChainEnv, a_comment, allow_all, build_chain
from sqlalchemy import text as sql_text
from store_support import StoreEnv
from store_support import env as _shared_env
from test_cli_support import workspace as _workspace_fixture

from labcairn.api import create_app
from labcairn.api.events import UnwiredEventSource
from labcairn.application import ApplicationContext
from labcairn.cli.workspace import (
    bind_workspace,
    locate,
    read_config,
)
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine, create_session_factory, session_scope
from labcairn.db.models import PaperProjectRow, PaperVersionRow, VersionEdgeRow
from labcairn.db.repository import TaskStore
from labcairn.security.approval import ApprovalLedger

pytestmark = pytest.mark.integration

env = _shared_env

#: The workspace fixture is the CLI's own: a workspace the console script
#: made, whose source root is the one ``sources ingest`` walks.
workspace = _workspace_fixture

#: The service's own origin, spelled as the guard allows it.
OWN_ORIGIN = "http://127.0.0.1:8000"

#: An origin that is not the service's own. A page on another site sends
#: exactly this.
FOREIGN_ORIGIN = "https://evil.example"

#: The baseline paragraph both fixture manuscripts carry, and the comment
#: written against it — the words the searches below run for.
PARAGRAPH = "The method estimates the parameter from a single observation."
COMMENT_TEXT = "Define the parameter."
COMMENT_ANCHOR = "the parameter"


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _write_two_manuscripts(workspace: Path) -> None:
    """Two manuscripts in the workspace's own ``materials`` source root.

    **One ingested file, one chain.** The CLI's ``task create`` ingests what
    the source roots hold; these two files are what it finds. The second
    manuscript carries no comments — a second round nobody has commented on
    — which is the smallest thing the two-version edge can hang between.
    """
    first = Fixture(
        name="manuscript",
        paragraphs=(PARAGRAPH,),
        comments=(a_comment("201", text=COMMENT_TEXT, anchor_text=COMMENT_ANCHOR),),
        purpose="The CLI ingest witness's first round.",
    )
    second = Fixture(
        name="manuscript-2",
        paragraphs=(PARAGRAPH,),
        purpose="The CLI ingest witness's second round.",
    )
    materials = workspace / "materials"
    built = workspace / "built"
    built.mkdir(exist_ok=True)
    (materials / "manuscript.docx").write_bytes(write_fixture(first, built).read_bytes())
    (materials / "manuscript-2.docx").write_bytes(write_fixture(second, built).read_bytes())


@dataclass(frozen=True, slots=True)
class CliChain:
    """The CLI workspace's chain: the project, its versions and its comment."""

    context: ApplicationContext
    project_id: str
    version_id: str
    second_version_id: str
    comment_text: str


def _project_and_versions(workspace: Path, task_id: str) -> CliChain:
    """The paper project, two versions, an edge and the recorded comment.

    **The rows are written the way the chain's fixtures write them, and the
    comment is recorded by the product's own reader.** ``paper_projects``,
    ``paper_versions`` and ``version_edges`` have no writer in ``src/`` yet,
    so a test that needs a project writes the rows itself — against the
    source ids the CLI's own ingestion just put in the ledger, with the
    hashes that ledger recorded. ``record_feedback`` then reads the first
    manuscript through the layer's own gate and writes the comment row, so
    the entry the index finds is one the product wrote.

    **The context comes back with the chain**, under a policy that allows
    everything: the CLI's *default* policy does not hand a test a free
    read, and the assertions here read rows and run searches, which is not
    what they are about. The ingest under test runs under the workspace's
    own policy, in the command's own process.
    """
    from labcairn.papers.feedback import record_feedback

    location = locate(workspace)
    config = read_config(location)
    engine = create_db_engine(location.root / config.database)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        rows = session.execute(
            sql_text("SELECT relative_path, source_id, content_sha256 FROM sources")
        ).all()
        by_name = {
            Path(str(relative)).name: (str(source_id), str(sha))
            for relative, source_id, sha in rows
        }
        first_id, first_sha = by_name["manuscript.docx"]
        second_id, second_sha = by_name["manuscript-2.docx"]
        session.add(
            PaperProjectRow(
                project_id="proj-1",
                workspace_id="ws-1",
                subject_pseudonym="subject-1",
                consent_ref=None,
                created_at=MOMENT,
            )
        )
        session.add(
            PaperVersionRow(
                version_id="ver-1",
                project_id="proj-1",
                source_id=first_id,
                source_content_sha256=first_sha,
                version_label_raw="manuscript.docx",
                stage_candidate="advisor_reviewed",
                status="resolved",
                created_at=MOMENT,
            )
        )
        session.add(
            PaperVersionRow(
                version_id="ver-2",
                project_id="proj-1",
                source_id=second_id,
                source_content_sha256=second_sha,
                version_label_raw="manuscript-2.docx",
                stage_candidate="draft",
                status="resolved",
                created_at=MOMENT,
            )
        )
        session.add(
            VersionEdgeRow(
                edge_id="edge-1",
                project_id="proj-1",
                parent_version_id="ver-1",
                child_version_id="ver-2",
                source="human",
                confidence=1.0,
                evidence_spans=[{"kind": "revision", "text": "revised"}],
                accepted_by="Dr. Chen",
                accepted_at=MOMENT,
                edge_version=1,
                superseded_by=None,
                created_at=MOMENT,
            )
        )
    engine.dispose()

    with _allowing_context(workspace, task_id) as context:
        record_feedback(
            context,
            project_id="proj-1",
            version_id="ver-1",
            now=MOMENT,
        )
        context.store.session.commit()
        return CliChain(
            context=context,
            project_id="proj-1",
            version_id="ver-1",
            second_version_id="ver-2",
            comment_text=COMMENT_TEXT,
        )


@contextmanager
def _allowing_context(workspace: Path, task_id: str) -> Iterator[ApplicationContext]:
    """A context over the CLI's workspace, under a policy that allows reads.

    **A test's reads are not what the default policy is for.** The
    workspace's own policy governs the command under test; this one governs
    the assertions, which read rows and search the index the command wrote.
    """
    location = locate(workspace)
    config = read_config(location)
    workspace_bound = bind_workspace(location, config, TaskId(uuid.UUID(task_id)))
    engine = create_db_engine(location.root / config.database)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            yield ApplicationContext(
                workspace=workspace_bound,
                store=TaskStore(session),
                policy=allow_all(),
                ledger=ApprovalLedger(),
            )
    finally:
        engine.dispose()


@pytest.fixture
def chain(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A chain: a manuscript with one comment, a project, two versions, an edge.

    **The rows are the product's own.** The scaffolding is the one the
    chain's tests use, so the project this route indexes is a project the
    product wrote rather than a row a test made up — and the comment is
    *recorded*, the product's own read, not a row inserted by hand.
    """
    from labcairn.papers.feedback import record_feedback

    built = build_chain(env.store(), tmp_path / "workspace", comments=(a_comment("201"),))
    record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    built.context.store.session.commit()
    return built


@pytest.fixture
def api(chain: ChainEnv) -> Iterator[tuple[TestClient, str]]:
    """The service over the chain's own task, with its session token."""
    app = create_app(chain.context, event_source=UnwiredEventSource())
    with TestClient(app) as wired:
        token = wired.get("/session").json()["token"]
        yield wired, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Origin": OWN_ORIGIN}


# --------------------------------------------------------------------------- #
# the API route
# --------------------------------------------------------------------------- #


def test_the_api_indexes_a_project_and_answers_a_search(
    chain: ChainEnv, api: tuple[TestClient, str]
) -> None:
    """``POST /trajectory/ingest`` indexes; ``GET /trajectory/search`` finds
    the comment — the wire serving the layer's own records."""
    client, token = api
    response = client.post(
        "/trajectory/ingest",
        json={"project_id": chain.project_id},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_id"] == chain.project_id
    assert body["entries_indexed"] == 1
    assert body["comment_entries"] == 1
    assert body["edit_entries"] == 0
    assert body["skipped_versions"] == 0
    assert body["ingested_at"]

    search = client.get(
        "/trajectory/search",
        params={"q": "Define the parameter"},
        headers=_auth(token),
    )
    assert search.status_code == 200, search.text
    hits = search.json()
    assert len(hits) == 1
    assert hits[0]["project_id"] == chain.project_id
    assert hits[0]["comment_text"] == COMMENT_TEXT
    assert hits[0]["source_version_id"] == chain.version_id
    assert hits[0]["source_sha256"], "the hit names the bytes it was read from"


def test_the_api_refuses_a_project_nobody_holds(
    chain: ChainEnv, api: tuple[TestClient, str]
) -> None:
    """A trajectory of a project the store does not hold is the layer's own
    refusal, named — not a 500 and not an index of nothing."""
    client, token = api
    response = client.post(
        "/trajectory/ingest",
        json={"project_id": "proj-nowhere"},
        headers=_auth(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "chain_project_not_found"


def test_the_api_refuses_a_body_without_the_project(api: tuple[TestClient, str]) -> None:
    """The contract's own field rule refuses a body that names no project.

    **A missing id and a blank id are the same refusal at the wire**, and
    both are the contract's 422 rather than the layer's 403: the request
    was not one the layer could be asked at all.
    """
    client, token = api
    missing = client.post("/trajectory/ingest", json={}, headers=_auth(token))
    assert missing.status_code == 422
    blank = client.post("/trajectory/ingest", json={"project_id": ""}, headers=_auth(token))
    assert blank.status_code == 422


def test_the_route_changes_something_so_the_session_guard_covers_it(
    chain: ChainEnv, api: tuple[TestClient, str]
) -> None:
    """The right origin is not consent to act, and a token is not a pass from
    a foreign origin — the same two guards every mutating route answers to."""
    client, token = api

    foreign = client.post(
        "/trajectory/ingest",
        json={"project_id": chain.project_id},
        headers={"Authorization": f"Bearer {token}", "Origin": FOREIGN_ORIGIN},
    )
    assert foreign.status_code == 403
    assert foreign.json()["reason"] == "origin_refused"

    tokenless = client.post(
        "/trajectory/ingest",
        json={"project_id": chain.project_id},
        headers={"Origin": OWN_ORIGIN},
    )
    assert tokenless.status_code == 401
    assert tokenless.json()["reason"] == "session_required"


def test_reingesting_the_same_project_is_the_same_answer(
    chain: ChainEnv, api: tuple[TestClient, str]
) -> None:
    """The index is rebuilt in place: a second ingest reports the same
    counts, and the search does not grow a second copy."""
    client, token = api
    first = client.post(
        "/trajectory/ingest",
        json={"project_id": chain.project_id},
        headers=_auth(token),
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/trajectory/ingest",
        json={"project_id": chain.project_id},
        headers=_auth(token),
    )
    assert second.status_code == 201, second.text
    assert second.json()["entries_indexed"] == first.json()["entries_indexed"]

    from labcairn.application.trajectory import search_trajectory

    hits = search_trajectory(chain.context, query="Define the parameter")
    assert len(hits) == 1, "one entry, not one per ingestion"


# --------------------------------------------------------------------------- #
# the CLI's sources ingest
# --------------------------------------------------------------------------- #


def _create_task(workspace: Path, title: str) -> str:
    """A task the CLI itself made, bound to the manuscripts written above."""
    from test_cli_support import run_cli

    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        title,
        "--objective",
        "Establish what the manuscript's history says.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--source-dir",
        "materials",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    return str(result.json()["task_id"])


def test_sources_ingest_indexes_the_projects_it_ingests(workspace: Path) -> None:
    """``sources ingest`` ingests the material and indexes the chain.

    **The report says what indexed.** A workspace holding one paper
    project's two manuscript versions answers with one trajectory outcome,
    carrying the layer's own counts — and a search through the same store
    finds the comment, so the index is the one the layer reads, not a
    report the CLI invented.
    """
    from test_cli_support import run_cli

    _write_two_manuscripts(workspace)
    task_id = _create_task(workspace, "Indexed by ingest")
    chain = _project_and_versions(workspace, task_id)

    result = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert result.returncode == 0, result.stderr
    report = result.json()

    # The ledger's own report is the base, untouched, field for field.
    assert report["readable"] == 2
    assert report["failures"] == []
    assert report["source_ids"], "the CLI ingested nothing"

    # The trajectory outcomes are the new half, and they are always present.
    outcomes = report["trajectory_projects"]
    assert [outcome["project_id"] for outcome in outcomes] == [chain.project_id]
    ingested = outcomes[0]["ingested"]
    assert ingested is not None
    assert ingested["entries_indexed"] == 1
    assert ingested["comment_entries"] == 1
    assert ingested["skipped_versions"] == 0
    assert outcomes[0]["refusal"] is None

    # And the index is the layer's: a search through the store finds the
    # comment the manuscript carries, without the CLI having been asked.
    from labcairn.application.trajectory import search_trajectory

    with _allowing_context(workspace, task_id) as context:
        hits = search_trajectory(context, query="Define the parameter")
    assert len(hits) == 1
    assert hits[0].comment_text == COMMENT_TEXT


def test_sources_ingest_reports_a_refused_project_and_still_succeeds(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One project whose index is refused is an outcome, not a failure.

    **The command does not become a fake success.** The material is
    ingested — that part worked — and the report carries the refusal beside
    it, with the layer's own reason, so a script sees both facts. The exit
    code is the command's own success, because the command's job (the
    ingestion) was done; the refused index is on its own line, the same way
    an unreadable file is.

    **The refusal is injected where the layer raises it**, the way
    ``tests/test_cli_path_refused_catch.py`` injects its refusal: the layer's
    own operation is made to refuse for one project, with the layer's own
    exception and reason, and the CLI is asked what it does with a refusal
    that arrives mid-report. The substitution is not a race, so the same
    measurement is the same measurement tomorrow. (A bare project — one the
    store holds but that has no versions — is *not* a refusal: the layer
    indexes nothing and says so. The refusal needs a layer that refuses.)
    """
    import json as json_module

    from typer.testing import CliRunner

    import labcairn.application.trajectory as trajectory_module
    from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
    from labcairn.cli.commands import app as cli_app

    _write_two_manuscripts(workspace)
    task_id = _create_task(workspace, "One project refused")
    chain = _project_and_versions(workspace, task_id)

    # A second paper project the store holds, alongside the real one.
    location = locate(workspace)
    config = read_config(location)
    engine = create_db_engine(location.root / config.database)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        session.add(
            PaperProjectRow(
                project_id="proj-bare",
                workspace_id="ws-1",
                subject_pseudonym="subject-2",
                consent_ref=None,
                created_at=MOMENT,
            )
        )
    engine.dispose()

    # The layer refuses this one project, by name — the same refusal shape
    # a project whose chain rows are unreachable would carry. The command
    # imports the operation inside its own body, so the patch lands where
    # the command looks it up.
    real_ingest = trajectory_module.ingest_paper_trajectory

    def selective(
        context: ApplicationContext,
        *,
        project_id: str,
        ingested_at: object = None,
    ) -> object:
        if project_id == "proj-bare":
            raise ApplicationRefusedError(
                ApplicationRefusal.CHAIN_PROJECT_NOT_FOUND,
                "the store holds no paper project with the id 'proj-bare'. A "
                "trajectory is a project's revision history, and a history of a "
                "project nobody holds is a history of nothing.",
            )
        return real_ingest(context, project_id=project_id)

    monkeypatch.setattr(trajectory_module, "ingest_paper_trajectory", selective)

    runner = CliRunner()
    result = runner.invoke(cli_app, ["--workspace", str(workspace), "sources", "ingest", "--json"])
    assert result.exit_code == 0, result.output
    report = json_module.loads(result.stdout)

    outcomes = {outcome["project_id"]: outcome for outcome in report["trajectory_projects"]}
    assert set(outcomes) == {chain.project_id, "proj-bare"}

    # The real project indexed; the refused one carries the layer's refusal.
    assert outcomes[chain.project_id]["ingested"] is not None
    assert outcomes[chain.project_id]["refusal"] is None

    refused = outcomes["proj-bare"]
    assert refused["ingested"] is None
    assert refused["refusal"] is not None
    assert refused["refusal"]["reason"] == "chain_project_not_found"
    assert "proj-bare" in refused["refusal"]["message"]

    # The prose says the same thing, because the picture is drawn from the
    # same model: the refused project's own line names it.
    plain = runner.invoke(cli_app, ["--workspace", str(workspace), "sources", "ingest"])
    assert plain.exit_code == 0, plain.output
    assert "proj-bare" in plain.stdout
    assert "chain_project_not_found" in plain.stdout
