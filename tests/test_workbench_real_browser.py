"""The workbench, in a real browser, against the service the CLI starts.

**What had never happened before this file.** Every web test in this repository stops
at the `fetch` boundary: `web/src/test/fakeApi.ts` answers `fetch` in jsdom, and the
component, the client, the paths and the session scheme are exercised exactly as they
are in a browser — *except the browser*. `docs/THREAT-MODEL.md` §6.1 says so plainly,
and `tests/test_workbench_live_service.py` closed the wire half of the gap with an
in-process ASGI transport, which opens no socket and renders nothing. This file is the
first time the built workbench was loaded by a browser and read the service through a
connection. It is `LC-P3-01` (§4.6 of `docs/plans/PHASE_3-work-orders.md`), and the
rows it is supposed to carry are named in the test that carries them.

**What is arranged, and where.** The service, the browser and the temporary workspace
come from `tests/workbench_serve_support.py`, whose arrangement §4.1 requires and
whose witnesses are in `tests/test_workbench_serve_helper.py`. This file asserts only
what a person would see.

**Where it skips, and why that is not a pass.** Playwright is not a declared dependency
of the product and the built workbench is git-ignored, so on a tree where neither is
present these tests skip and name the missing piece. The browser channel is judged the
same way, by the launch the driver performs: a machine without the pinned channel (an
Ubuntu runner carries no Edge) makes the launch fail before any process is spawned,
with a message that names the channel, and that failure is this file's skip reason. A
skip is not a discharged row: the environment record (named by §4.3) is where the run
that *did* launch a browser says what it launched, and the run that skipped says it
skipped.

**The gap this run found is asserted, not glossed.** The service `labcairn serve`
builds has no event source, so the Events panel cannot be live on it. One test below
watches the panel say that, because a panel that looked connected on a service with
nothing to stream would be the screen claiming what the service does not have.
"""

# --------------------------------------------------------------------------- #
# Assertion standing — measured 2026-11-14. Read this before editing below.
# --------------------------------------------------------------------------- #
#
# **The assertions in this file are not of equal standing, and this header
# says which is which.** The standing of every assertion was measured, not
# judged: the product each assertion watches was made to lie (the built page,
# the client, or the service), the assertion under test was knocked out, and
# the file was run to see whether any other assertion turned red. A red run
# with the assertion gone means the property has a second guard here; a green
# run means the assertion was the property's only root in this file.
#
# **Unique roots** — knock one out and its property is unguarded here:
#   * renders test: the origin checks (scheme, netloc) are the only guard
#     that the page was loaded from the service's own origin (§4.6 row 4's
#     first half); the non-placeholder title check is the only guard that the
#     header drew a real title at all.
#   * shows-the-task test: the title, objective and criterion checks are each
#     the only guard of its own field on the screen.
#   * every-read test: the nine-path list is the only guard that the page
#     makes every declared read (§4.6 row 9); the all-answered-200 check is
#     the only guard that the service answers those reads.
#   * no-outbound-request test: the loopback check is the only guard of the
#     footer's "the local API and nothing else" promise.
#   * session test: the token-path-on-the-page check and the
#     token-not-rendered check are each the only guard of its own half (the
#     session read is visible; the token itself never reaches the page).
#   * selection test: the Projects-panel selected-flag checks are the only
#     guard that the page's own selection marking is honest; the pointer
#     check and the same-document check are the only guards that the
#     workspace's pointer followed and that page and CLI print one document.
#   * environment test: the driver-resolved-cache check is the only guard
#     that the browser-cache pin held; the replaced-cache control witnesses
#     that the pin overrode something. The driver-version, channel and
#     browser-version checks are each the only guard of its own field.
#   * approval test: the no-second-Grant check and the refused-second-grant
#     check are the only guards that one approval cannot be answered twice
#     (the screen half and the API half of the same property).
#   * chain-comment test: the issue-key listing check is the only guard that
#     the panel draws the chain's keys; the comment-words check and the
#     version-id check are each the only guard of its own field.
#
# **Backed up** — a second assertion here also fails for the breakage:
#   * the stream-refusal status (`== 403`) appears in the every-read test and
#     again in the Events-panel test; either catches a stream read whose
#     refusal stopped being a response.
#   * the Events panel's not-live check and its interrupted/disconnected
#     check both catch a panel that reports the stream live; but only the
#     interrupted/disconnected check demands the honest sentence, so neither
#     is redundant.
#   * the placeholder-title check and the title-equals-the-CLI check both
#     catch a header that fell back to the placeholder.
#   * the session-read-made check is backed up by the nine-path list; the
#     session-answered-200 check by the every-read test's answered check.
#   * the same-document check in the shows-the-task test and the one in the
#     selection test back each other up (before and after a selection).
#
# **What this header does not claim.** A skip is still not a pass: the
# unique-root list holds for a run in which this file actually drove a
# browser. A backup inside this file is not the only backup the project has —
# `tests/test_workbench_live_service.py` and the web unit suite watch several
# of the same properties at their own layers.

from __future__ import annotations

import importlib.metadata
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
import workbench_serve_support as support
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from workbench_serve_support import (
    WEB_DIST_DIR,
    BrowserLaunch,
    CliResult,
    ServedWorkbench,
    browser_cache_dir,
    channel_skip_reason,
    run_cli,
    start_served_workbench,
)

from labcairn.application.approvals import ApprovalRequest, ApprovalUse, request_approval
from labcairn.application.chain import record_feedback
from labcairn.cli.workspace import application_context, locate, read_config
from labcairn.core.ids import TaskId
from labcairn.papers.feedback import set_issue_key
from labcairn.security.capabilities import CapabilityId

pytestmark = pytest.mark.e2e

#: The reads `web/src/api/paths.ts` declares for the workbench, in the spelling the
#: service uses. §4.6 row 9 asks that each of them be made against the real service,
#: so this list is asserted against what the browser actually requested.
DECLARED_READS: tuple[str, ...] = (
    "/health",
    "/session",
    "/tasks",
    "/task",
    "/plan",
    "/steps",
    "/sources",
    "/artifacts",
    "/events/stream",
)

#: The reads the panel-level comparison is about: everything except the stream, which
#: is the one read the CLI-served service cannot answer (§4.6 row 9's exception).
ANSWERED_READS: tuple[str, ...] = tuple(path for path in DECLARED_READS if path != "/events/stream")

#: The service is read eight times by one render; the reads are batched, and the page
#: settles in well under a second on this machine. This is a ceiling on the wait, not
#: a measurement of the page.
SETTLE_SECONDS = 3.0

FIRST_TASK = ("Browser baseline first", "What the page shows first.", "The title is on the screen.")
SECOND_TASK = (
    "Browser baseline second",
    "What the page shows after the switch.",
    "The title changed.",
)


def _make_workspace(
    root: Path,
    *tasks: tuple[str, str, str],
    source_dir: str | None = None,
    material: dict[str, str] | None = None,
) -> Path:
    """A workspace and its tasks, made by the CLI a person would use.

    :param source_dir: a directory of supplied material, workspace-relative, bound as
        a source root by ``task create --source-dir``. The consent test needs material
        the policy will recognise as material: a consent question about the workspace
        root itself is refused, and that refusal is the policy working.
    :param material: what to write in that directory first. Synthetic, written here.
    """
    if source_dir is not None and material is not None:
        directory = root / source_dir
        directory.mkdir(parents=True, exist_ok=True)
        for name, text in material.items():
            (directory / name).write_text(text, encoding="utf-8")
    made = run_cli("--workspace", str(root), "init")
    assert made.returncode == 0, f"labcairn init refused: {made.stderr}"
    for title, objective, criterion in tasks:
        arguments = [
            "--workspace",
            str(root),
            "task",
            "create",
            "--title",
            title,
            "--objective",
            objective,
            "--criterion",
            criterion,
            "--json",
        ]
        if source_dir is not None:
            arguments += ["--source-dir", source_dir]
        created = run_cli(*arguments)
        assert created.returncode == 0, f"labcairn task create refused: {created.stderr}"
    return root


def _current_task(workspace: Path) -> dict[str, Any]:
    """What the CLI says the workspace is about, with no ``--task`` given."""
    result: CliResult = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert result.returncode == 0, result.stderr
    body: dict[str, Any] = result.json()
    return body


@dataclass
class WorkbenchRun:
    """One browser, one service, one workspace: the baseline's whole arrangement."""

    served: ServedWorkbench
    browser: Any
    facts: BrowserLaunch
    workspace: Path


def _require_build() -> None:
    if not WEB_DIST_DIR.is_dir():
        pytest.skip(
            f"{WEB_DIST_DIR} does not exist. The build is made by `pnpm install "
            "--frozen-lockfile` and `pnpm build` in web/ and is git-ignored; §4.2 asks a "
            "run to name the build it loaded, not to assume one was there."
        )


@pytest.fixture(scope="module")
def workbench(tmp_path_factory: pytest.TempPathFactory) -> Iterator[WorkbenchRun]:
    """The service, the browser and the workspace, started once for this file.

    **Started in this order on purpose.** The driver is started before the service so
    that a machine without Playwright skips before a workspace is built and a port is
    opened; whatever was opened is closed on the way out, because a service left
    running holds the workspace's store and its port against the next test file.
    """
    _require_build()
    root = tmp_path_factory.mktemp("browser")
    playwright: Any = None
    browser: Any = None
    served: ServedWorkbench | None = None
    try:
        playwright = support.start_playwright()
        workspace = _make_workspace(root / "workspace", FIRST_TASK, SECOND_TASK)
        served = start_served_workbench(workspace=workspace, dist_dir=WEB_DIST_DIR)
        browser, facts = support.launch_workbench_browser(playwright)
    except Exception as error:
        if browser is not None:
            browser.close()
        if playwright is not None:
            playwright.stop()
        if served is not None:
            served.stop()
        # **The channel's absence is the driver's own verdict.** A machine
        # without the pinned channel (an Ubuntu runner carries no Edge) fails
        # the launch above before any process is spawned, with a message that
        # names the channel. That failure is this file's skip reason, so the
        # run on such a machine is a named skip and not a red; any other launch
        # failure keeps its own "no browser to drive" report.
        missing_channel = channel_skip_reason(error)
        if missing_channel is not None:
            pytest.skip(missing_channel)
        pytest.skip(f"no browser to drive: {type(error).__name__}: {str(error)[:400]}")
    try:
        yield WorkbenchRun(served=served, browser=browser, facts=facts, workspace=workspace)
    finally:
        browser.close()
        playwright.stop()
        assert served is not None
        served.stop()


def _load(run: WorkbenchRun) -> tuple[Any, list[str], dict[str, int]]:
    """Open the workbench in the live browser, and record what it asked for.

    :returns: the page, the URLs it requested, and the status of each answered one.
    """
    page = run.browser.new_page()
    requested: list[str] = []
    answered: dict[str, int] = {}
    page.on("request", lambda request: requested.append(str(request.url)))
    page.on(
        "response", lambda response: answered.__setitem__(str(response.url), int(response.status))
    )
    page.goto(f"{run.served.origin}/", wait_until="load")
    page.wait_for_selector("h1.workbench__title", timeout=15000)
    page.wait_for_timeout(int(SETTLE_SECONDS * 1000))
    return page, requested, answered


def _paths(requested: list[str]) -> list[str]:
    """The paths the browser asked for, in the spelling the service declares."""
    return [urlparse(url).path for url in requested]


def _answers(answered: dict[str, int]) -> dict[str, int]:
    """Statuses keyed by path rather than by the full URL the browser used."""
    return {urlparse(url).path: status for url, status in answered.items()}


# --------------------------------------------------------------------------- #
# §4.6 rows 4, 10: it rendered, and it rendered the task the CLI reported
# --------------------------------------------------------------------------- #


def test_the_workbench_renders_in_a_real_browser_at_the_service_s_own_origin(
    workbench: WorkbenchRun,
) -> None:
    """The built page, loaded from the service's own origin, drew its panels."""
    page, _requested, _answered = _load(workbench)
    try:
        assert urlparse(page.url).scheme == "http"
        assert urlparse(page.url).netloc == urlparse(workbench.served.origin).netloc, (
            f"the page was loaded from {page.url}, not from the service at "
            f"{workbench.served.origin} — §4.6 row 4 is about the built page served by "
            "the service, not by a development server beside it"
        )
        title = page.inner_text("h1.workbench__title")
        assert title, "the workbench rendered no title, so React did not run"
        assert title != "LabCairn", (
            "the header fell back to the placeholder title, which is what the page "
            "shows when the state read did not answer"
        )
        panels = page.locator("section.panel")
        count = panels.count()
        assert count >= 8, f"the workbench drew {count} panels; it declares more than eight"
    finally:
        page.close()


def test_the_page_shows_the_task_the_cli_reports_for_the_same_workspace(
    workbench: WorkbenchRun,
) -> None:
    """§4.6 row 10: the CLI and the browser read one service, one store.

    The comparison is with `task status --json`, the CLI's own answer for the
    workspace, because the screen is the API's answer and the API's answer is the
    store's state. A page that held a cached copy would still match the API and fail
    here only if the two disagreed — which is why the disagreement is created for real
    in the selection test below rather than imagined here.
    """
    page, _requested, _answered = _load(workbench)
    try:
        cli = _current_task(workbench.workspace)
        task = cli["task"]
        assert page.inner_text("h1.workbench__title") == task["title"]
        goal = page.inner_text(".workbench__goal")
        assert task["goal"]["objective"] in goal
        assert task["goal"]["success_criterion"] in goal
        assert workbench.served.get("/task").json()["task"] == task, (
            "the browser's state and the CLI's state are not the same document"
        )
    finally:
        page.close()


# --------------------------------------------------------------------------- #
# §4.6 rows 4, 9: the reads the page made, and where they went
# --------------------------------------------------------------------------- #


def test_the_page_makes_every_read_the_workbench_declares(workbench: WorkbenchRun) -> None:
    """§4.6 row 9: each read in the §4.4 list, made by the page, against the service."""
    page, requested, answered = _load(workbench)
    try:
        paths = _paths(requested)
        statuses = _answers(answered)
        missing = [path for path in DECLARED_READS if path not in paths]
        assert not missing, (
            f"the page never asked for: {missing}. It requested {sorted(set(paths))}"
        )
        unanswered = [
            (path, statuses.get(path)) for path in ANSWERED_READS if statuses.get(path) != 200
        ]
        assert not unanswered, f"the service did not answer these reads: {unanswered}"
        assert statuses["/events/stream"] == 403, (
            "the stream read no longer answers its refusal as a response. A 200 here "
            "means the route started a response before deciding it had nothing to read "
            "from — the shape O6 was measured in (docs/acceptance/"
            "o6-event-stream-stall-2026-11-10.md). Any other status means this read has "
            f"changed shape and needs re-measuring: {statuses['/events/stream']}"
        )
    finally:
        page.close()


def test_no_request_the_page_made_left_the_machine(workbench: WorkbenchRun) -> None:
    """The footer's claim — *the local API and nothing else* — checked on the wire.

    `web/index.html` promises no analytics, no remote fonts and no CDN scripts, and the
    footer repeats it. The promise is about outbound requests, and an outbound request
    is exactly the thing a page acquires without anyone deciding to add one.
    """
    page, requested, _answered = _load(workbench)
    try:
        foreign = [
            url
            for url in requested
            if urlparse(url).scheme != "http" or urlparse(url).hostname != "127.0.0.1"
        ]
        assert not foreign, f"the page contacted something besides the loopback service: {foreign}"
    finally:
        page.close()


# --------------------------------------------------------------------------- #
# §4.6 row 11: the session token, read by the page at the service's own origin
# --------------------------------------------------------------------------- #


def test_the_page_reads_the_session_at_the_service_s_own_origin(workbench: WorkbenchRun) -> None:
    """The page knows where the token is, and does not show the token.

    The footer names the file the service wrote the token to; that sentence is only
    true if the page read `/session` and got the answer, so it is the witness that the
    read happened at the page's own origin. The token itself must not appear on the
    page: the client holds it in a module-level holder and presents it as a header, for
    exactly the reason `web/src/api/client.ts` gives — React state is readable from the
    outside.
    """
    page, requested, answered = _load(workbench)
    try:
        assert "/session" in _paths(requested)
        assert _answers(answered)["/session"] == 200
        body = page.inner_text("body")
        assert str(workbench.served.session_token_path) in body, (
            "the page did not name the token file the service wrote, so the session "
            f"read is not visible anywhere on it. Footer text: {body[-400:]}"
        )
        assert workbench.served.session_token() not in body, (
            "the token itself was rendered on the page"
        )
    finally:
        page.close()


# --------------------------------------------------------------------------- #
# §4.6 row 12 and §4.8's first bullet: the page moves the selection, the CLI agrees
# --------------------------------------------------------------------------- #


def test_the_page_moves_the_service_s_selection_and_the_cli_reports_it(
    workbench: WorkbenchRun,
) -> None:
    """A change made in a real browser, seen by the other surface.

    The workspace holds two tasks and the service is bound to the one the CLI created
    last. The page is asked to select the *other* one, and the test then asks three
    surfaces the same question: the CLI's `task status` without `--task`, the service's
    `GET /health`, and the page's own header. All three must agree, and the state read
    must be the same document the CLI prints — field for field, as the live-service
    witness established, now through a socket and a render.
    """
    page, _requested, _answered = _load(workbench)
    try:
        before = _current_task(workbench.workspace)["task"]
        tasks = workbench.served.get("/tasks").json()
        other = next(task for task in tasks if task["task_id"] != before["task_id"])

        button = page.get_by_role("button", name="Select").first
        button.click()

        deadline = time.monotonic() + 20.0
        while (
            time.monotonic() < deadline and page.inner_text("h1.workbench__title") != other["title"]
        ):
            page.wait_for_timeout(200)

        assert page.inner_text("h1.workbench__title") == other["title"], (
            f"the page still shows {before['title']!r} after the selection request"
        )
        assert workbench.served.get("/health").json()["task_id"] == other["task_id"]
        assert _current_task(workbench.workspace)["task"]["task_id"] == other["task_id"], (
            "the page selected a task the workspace's own pointer did not follow"
        )
        assert workbench.served.get("/task").json() == _current_task(workbench.workspace), (
            "the state the page draws and the state the CLI prints are not the same "
            "document after the switch"
        )
        flags = page.locator("li.record", has_text=other["title"]).locator(".record__flag")
        assert flags.count() == 1, (
            f"the Projects panel marks {flags.count()} of the records for the task the page "
            f"selected ({other['title']!r})"
        )
        assert flags.first.inner_text().lower() == "selected"
        assert (
            page.locator("li.record", has_text=before["title"]).locator(".record__flag").count()
            == 0
        ), "the task the page moved away from is still marked selected"
    finally:
        page.close()


# --------------------------------------------------------------------------- #
# §4.2: the environment, named by the run that used it
# --------------------------------------------------------------------------- #


def test_the_run_names_the_browser_the_channel_and_the_cache_it_actually_used(
    workbench: WorkbenchRun,
) -> None:
    """§4.2's rows, taken from the run rather than written down before it.

    **The cache row is the one that matters on this machine.** `PLAYWRIGHT_BROWSERS_PATH`
    is set for every process here to another project's browser cache; the helper pins it
    before the driver starts, and the driver's own answer for where its browser lives is
    what shows the pin held. A run that measured a browser belonging to a different
    project would report a baseline nobody ran.
    """
    facts = workbench.facts
    pinned = browser_cache_dir()

    assert facts.driver_version == importlib.metadata.version("playwright")
    assert facts.channel == support.BROWSER_CHANNEL == "msedge"
    assert facts.browser_version, "the driver reported no browser version"

    assert Path(facts.cache_in_force) == pinned
    assert str(pinned) in facts.driver_default_cache, (
        f"the driver resolved its browser to {facts.driver_default_cache}, outside the "
        f"project's own cache {pinned} — the inherited PLAYWRIGHT_BROWSERS_PATH won"
    )
    assert pinned.is_absolute() and support.REPO_ROOT not in pinned.parents, (
        f"the browser cache is inside the repository under review: {pinned}"
    )

    # The control that shows the pin did something. The variable *now* holds the pin, so
    # reading it back would compare the pin with itself; what the helper recorded is the
    # value the machine carried before it was replaced. On a machine that carried
    # nothing, there is nothing to override and the assertion above is the whole claim.
    replaced = facts.cache_replaced
    if replaced is not None:
        assert Path(replaced) != pinned, (
            f"the helper recorded {replaced} as replaced, but nothing was overridden"
        )
        assert str(Path(replaced)) not in facts.driver_default_cache, (
            f"the driver's browser lives under the inherited cache {replaced}: "
            f"{facts.driver_default_cache}"
        )


# --------------------------------------------------------------------------- #
# §4.8's third bullet, §4.4 row 13: an approval answered from the page
# --------------------------------------------------------------------------- #

CONSENT_TASK = (
    "Consent baseline",
    "Whether a page can answer a consent question the service asked.",
    "The approval is recorded as granted.",
)

#: The material the consent question is about. Written by this file, in the
#: workspace's own source root: synthetic, because §4.1 forbids real advisor material
#: in the automated baseline.
CONSENT_MATERIAL = {
    "note.md": "# Synthetic note\n\nWritten by the baseline. Not advisor material.\n"
}

#: The operation the consent question covers. The shape is the Figure line's own —
#: `web/src/views/FigureView.tsx` asks for `analysis.run` against a dataset root with a
#: recipe — because that is the consent this product's own surfaces ask for.
_CONSENT_ARGUMENTS = {"operator_id": "mean", "parameters": {}, "recipe": "figure.recipe.json"}


@pytest.fixture(scope="module")
def consent_run(
    workbench: WorkbenchRun,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[ServedWorkbench, str]]:
    """A second service, with one consent question waiting for an answer from the page.

    **How the question is asked, and why not through the page.** The page's own way to
    ask is the Figure panel, whose form needs a chart recipe and a dataset root this
    synthetic workspace does not have. The service's own door, ``POST /approvals``, was
    tried first and measured: on 2026-11-08 it refused with
    ``permission_denied … default_deny`` for ``source.read`` on a bound source root, so
    an HTTP client cannot put a question on a fresh workspace's ledger without a policy
    rule that permits the capability. That refusal is itself part of §4.7's gap list.
    §4.4 row 13 is about the **answer** being taken from the page, so the question is
    asked the way the product asks it in its own layer — the same
    :func:`labcairn.application.approvals.request_approval` the service calls — before
    the service starts, and the browser is what answers it.
    """
    root = tmp_path_factory.mktemp("consent")
    workspace = _make_workspace(
        root / "workspace",
        CONSENT_TASK,
        source_dir="sources/synthetic",
        material=CONSENT_MATERIAL,
    )
    task_id = _current_task(workspace)["task"]["task_id"]
    approval_id = _ask_for_consent(workspace, task_id)

    served = start_served_workbench(workspace=workspace, dist_dir=WEB_DIST_DIR)
    try:
        yield served, approval_id
    finally:
        served.stop()


def _ask_for_consent(workspace: Path, task_id: str) -> str:
    """Put one consent question on the task's ledger, through the layer that owns it."""
    location = locate(workspace)
    config = read_config(location)
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        asked = request_approval(
            context,
            ApprovalRequest(
                use=ApprovalUse(
                    capability=CapabilityId.ANALYSIS_RUN,
                    arguments=dict(_CONSENT_ARGUMENTS),
                    root_id="source:0",
                    resource_key="note.md",
                ),
                # The window sits in the future of the clock the workspace's own rows
                # are stamped with: `task create` writes real instants, not the suite's
                # frozen one. An approval whose window closed before it was answered is
                # refused on grant, and that property is witnessed in
                # tests/test_application_approvals.py.
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                stage_name="consent-baseline",
            ),
        )
        return str(asked.approval.approval_id)


def test_an_approval_answered_from_the_page_is_recorded_and_a_second_answer_is_refused(
    workbench: WorkbenchRun,
    consent_run: tuple[ServedWorkbench, str],
) -> None:
    """§4.4 row 13: the answer the page gave is the state the contract promises.

    Three things are checked, and each fails for a different breakage: the recorded
    state is `granted`; the page says so on the screen; and the page no longer offers a
    second answer, because a second grant of one approval would be an operation nobody
    asked for. The API is asked the same second grant directly, so the refusal is seen
    from both sides of the screen.
    """
    served, approval_id = consent_run
    before = served.get("/task").json()
    pending = [item for item in before["approvals"] if item["approval_id"] == approval_id]
    assert pending and pending[0]["state"] == "pending", before["approvals"]

    page = workbench.browser.new_page()
    try:
        page.goto(f"{served.origin}/", wait_until="load")
        page.wait_for_selector("h1.workbench__title", timeout=15000)
        page.wait_for_timeout(int(SETTLE_SECONDS * 1000))

        grant = page.get_by_role("button", name="Grant")
        assert grant.count() == 1, (
            f"the Approval panel offered {grant.count()} Grant buttons for one pending approval"
        )
        grant.first.click()

        deadline = time.monotonic() + 20.0
        recorded: dict[str, Any] = {}
        while time.monotonic() < deadline:
            approvals = served.get("/task").json()["approvals"]
            recorded = next((item for item in approvals if item["approval_id"] == approval_id), {})
            if recorded.get("state") == "granted":
                break
            page.wait_for_timeout(200)

        assert recorded.get("state") == "granted", f"the approval was not granted: {recorded}"

        page.wait_for_timeout(int(SETTLE_SECONDS * 1000))
        # The panel's flags are upper-cased by the stylesheet, and other panels carry
        # flags of their own (the plan's stage evidence reads PENDING), so the claim is
        # read off the Approval panel and compared case-insensitively.
        approval_panel = page.locator("section.panel", has_text="Approval")
        flags = approval_panel.locator(".record__flag")
        shown = [flags.nth(index).inner_text().lower() for index in range(flags.count())]
        assert "granted" in shown, f"the Approval panel shows {shown}, not the recorded state"
        assert page.get_by_role("button", name="Grant").count() == 0, (
            "the panel still offers a Grant for an approval that has been answered"
        )

        refused = served.post(f"/approvals/{approval_id}/grant", {})
        assert refused.status == 403, (
            f"a second grant was served: {refused.status} {refused.body[:200]}"
        )
        assert refused.json()["reason"] == "approval_refused", refused.body
    finally:
        page.close()


# --------------------------------------------------------------------------- #
# the gap this run measured, asserted
# --------------------------------------------------------------------------- #


def test_the_events_panel_says_the_stream_was_refused_on_a_service_that_has_none(
    workbench: WorkbenchRun,
) -> None:
    """The screen and the service now agree: the panel reports the refusal.

    What this row used to measure (2026-11-08) was a disagreement. The page's stream
    read resolved with ``200 text/event-stream`` and carried nothing — the service
    ``labcairn serve`` builds was given no event source, and the route raised its
    refusal *after* its own headers were sent — while the Events panel, whose states
    are ``connecting``, ``live``, ``reconnecting`` and ``disconnected``, reported
    **"the event stream is live"**. The panel was honest about the stream it had seen
    and wrong about the service, because there was nothing to deliver the log from.

    **What is asserted now, and why it is the same row.** The refusal reaches the
    reader: the page's read answers ``403`` with the refusal body, the client turns a
    non-``ok`` stream response into an ``ApiRefusal``, and the panel draws an
    interrupted or disconnected line rather than a live one. The disagreement is gone,
    so the witness asserts its replacement — and it keeps asserting the service's
    half, the ``not_implemented`` on ``GET /events``, because **the stream is still
    unwired**: a panel that reported ``live`` on this service would be reporting an
    event source the service does not have, which is the same lie in new clothes.

    Closing the disagreement does not wire the stream. ``labcairn serve`` still passes
    no event source (`src/labcairn/cli/commands.py`), and that remains the owner's
    call.
    """
    page, _requested, answered = _load(workbench)
    try:
        panel = page.locator("section.panel", has_text="Events")
        assert panel.count() >= 1, "the Events panel was not drawn at all"
        status = panel.locator("p.panel__status, p.panel__error")
        assert status.count() >= 1, "the Events panel drew no status line"
        text = status.first.inner_text()

        assert _answers(answered)["/events/stream"] == 403, (
            "the page's stream read no longer carries its refusal as a response, so the "
            "disagreement this row records has changed shape: "
            f"{_answers(answered)['/events/stream']}"
        )
        assert "is live" not in text.lower(), (
            f"the Events panel reports the stream live on a service that has no event "
            f"source ({text!r}); the service refused the read, so the reader is being "
            "told the log of the work is being delivered when nothing can deliver it"
        )
        assert "interrupted" in text.lower() or "disconnected" in text.lower(), (
            f"the Events panel neither reports the stream interrupted nor disconnected "
            f"({text!r}); on a service whose stream read is refused, one of those two is "
            "the only honest sentence, and the row needs re-measuring against whatever "
            "the panel says instead"
        )

        refused = workbench.served.get("/events?follow=false")
        assert refused.status == 403, refused.body[:200]
        assert refused.json()["reason"] == "not_implemented", refused.body[:200]
    finally:
        page.close()


# --------------------------------------------------------------------------- #
# §4.8's second bullet, §4.4 row 10: the comment the chain holds, on the screen
# --------------------------------------------------------------------------- #

CHAIN_TASK = (
    "Chain baseline",
    "Whether the chain's comment is visible in the view that reads it.",
    "The comment's own words are on the screen.",
)

#: The chain's key for the one synthetic comment this fixture seeds. A key is a
#: name a person gave an issue; the words are the comment's, and they are what
#: §4.8's second bullet asks to see.
ISSUE_KEY = "p3-01-baseline"

CHAIN_COMMENT_TEXT = "Please define the parameter before the first paragraph ends."


@pytest.fixture(scope="module")
def chain_run(
    workbench: WorkbenchRun,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[ServedWorkbench, ChainEnv]]:
    """A second service, in a workspace whose chain holds one comment.

    **The comment is written the way the product writes one.** The chain's door is
    `application.chain.record_feedback`, which reads the comments a manuscript
    version actually carries and refuses an anchor that no longer matches its
    text; the manuscript itself is the synthetic fixture `feedback_chain_fixtures`
    builds (one DOCX, one comment, no advisor material — §4.1). It is written
    **before** the service starts, through the same layer, into the same
    workspace store the service then serves — the browser witnesses what a
    reader of this workspace would see, not what a test process held in memory.

    **The panel is form-driven, and the form is part of the property.** The
    Trajectory panel lists the chain's issue keys for a project and draws a
    comment only under a key the reader names. So the browser names the project,
    asks for the list, picks the key out of what the service listed, and only
    then asserts the words — a page that invented a key or drew the comment
    without the chain's answer would fail here.
    """
    root = tmp_path_factory.mktemp("chain")
    workspace = _make_workspace(root / "workspace", CHAIN_TASK)
    task_id = _current_task(workspace)["task"]["task_id"]
    location = locate(workspace)
    config = read_config(location)
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        built = build_chain(
            context.store,
            workspace,
            comments=(a_comment(ISSUE_KEY, text=CHAIN_COMMENT_TEXT),),
        )
        feedback = record_feedback(
            built.context,
            project_id=built.project_id,
            version_id=built.version_id,
            now=datetime.now(UTC),
        )[0]
        # A key is a person's judgement and is given, never derived: the chain's
        # rows hold no key until somebody names one, and the Issues panel lists
        # keyed comments only.
        set_issue_key(
            built.context,
            feedback_id=feedback.feedback_id,
            issue_key=ISSUE_KEY,
            now=datetime.now(UTC),
        )

    served = start_served_workbench(workspace=workspace, dist_dir=WEB_DIST_DIR)
    try:
        yield served, built
    finally:
        served.stop()


def test_a_chain_comment_is_visible_in_the_view_that_reads_it(
    workbench: WorkbenchRun,
    chain_run: tuple[ServedWorkbench, ChainEnv],
) -> None:
    """§4.4 row 10's second half: the comment, in the workbench, in a real browser.

    Three steps, each of which fails for its own breakage: the Issues panel lists
    the chain's key for the project; picking that key draws the trajectory; and
    the trajectory carries the comment's own words. The last is the assertion
    §4.8's second bullet asks for — an imported comment-bearing sample, visible
    in the view that reads it.
    """
    served, built = chain_run
    page = workbench.browser.new_page()
    try:
        page.goto(f"{served.origin}/", wait_until="load")
        page.wait_for_selector("h1.workbench__title", timeout=15000)
        page.wait_for_timeout(int(SETTLE_SECONDS * 1000))

        # The form is the Trajectory panel's own: the Issues panel has no input of
        # its, it answers the project the Trajectory panel named.
        trajectory = page.locator("section.panel", has_text="Trajectory").first
        trajectory.get_by_label("Project id").fill(built.project_id)
        trajectory.get_by_role("button", name="List the issues").click()

        issues = page.locator("section.panel", has_text="Issues").first
        listed = issues.get_by_role("button", name="Draw this issue")
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline and listed.count() == 0:
            page.wait_for_timeout(200)
        assert listed.count() >= 1, (
            "the Issues panel listed no issue for the project the chain holds"
        )

        names = issues.locator(".record__name")
        shown = [names.nth(index).inner_text() for index in range(names.count())]
        assert ISSUE_KEY in shown, f"the Issues panel listed {shown}, not the chain's key"

        listed.first.click()

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline and CHAIN_COMMENT_TEXT not in trajectory.inner_text():
            page.wait_for_timeout(200)

        drawn = trajectory.inner_text()
        assert CHAIN_COMMENT_TEXT in drawn, (
            f"the trajectory did not carry the comment's own words; the panel drew: {drawn[:600]!r}"
        )
        assert built.version_id in drawn, (
            "the trajectory did not name the manuscript version the comment was written against"
        )
    finally:
        page.close()
