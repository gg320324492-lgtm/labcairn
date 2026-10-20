"""G4's exit demonstration is run by a test, so it cannot quietly stop working.

Neither ``g1_exit_demo.py`` nor ``g2_exit_demo.py`` is run by CI or by any
test, and the independent review of G3 named that as a hole. This file runs
**G4's** demonstration -- the clean-clone developer launch, and the three
surfaces producing the same versioned report -- as a subprocess, the way a
person runs it, and asserts that it exits zero.

**The exit code is the assertion that matters.** Every claim the
demonstration makes is carried by a ``check()`` that raises rather than warns,
so a non-zero exit means a guard stopped working and a zero exit means every
one of them still holds. A test that only read the output would be testing the
prose.

The output is asserted too, but for the things the exit code cannot say on
its own: that the eight steps actually ran, that the refusals were refusals
with a reason rather than crashes, that the two surfaces were compared against
**one** store, and that the demonstration said what it did not exercise.

**It runs once for the whole module.** The demonstration walks the whole path
-- a workspace, a database, a figure drawn by matplotlib, four exported forms
-- and takes about fifteen seconds. Running it again for every assertion would
multiply that for no extra evidence.

**The demonstration's workspace is outside the repository.** That is asserted
here rather than assumed: a workspace inside the checkout would make the run
depend on the tree it is running in, and the demonstration's own claim is that
it is a clean clone.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_developer_launch import run_cli

from labcairn.api.app import create_app
from labcairn.cli.workspace import application_context, locate, read_config
from labcairn.core.ids import TaskId
from labcairn.recovery.resume import STALE_REASON

#: The demonstration, as a person runs it.
DEMO: Path = Path(__file__).parent.parent / "examples" / "g4_exit_demo.py"

#: The eight steps, in the order the acceptance clause names them. A step that
#: stopped running would leave its heading out of the output, so their presence
#: is a fact about what the demonstration did rather than a fact about its
#: prose.
STEPS: tuple[str, ...] = (
    "1. labcairn init",
    "2. labcairn doctor",
    "3. A material, and a task it is bound to",
    "4. The report",
    "5. The three surfaces agree",
    "6. A refresh changes nothing, and repeats nothing",
    "7. An approval cannot be spoofed from another origin",
    "8. The material changes, and the report says so",
)

#: The floor on the number of checks. The demonstration makes thirty-nine; a
#: demonstration that made fewer would have had whole claims removed, and the
#: count is the only thing that would say so.
MINIMUM_CHECKS: int = 30


@pytest.fixture(scope="module")
def demonstration(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, once for the whole module.

    Its own temporary workspace and database, so it leaves nothing behind and
    needs nothing from the test.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set because the child's output
    encoding and terminal width are otherwise the machine's business, and
    neither is a fact about the demonstration.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return subprocess.run(
        [sys.executable, str(DEMO)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=900,
        cwd=repo_root,
    )


@pytest.mark.e2e
def test_the_exit_demonstration_runs_and_every_check_holds(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration exits zero, and every claim it makes was made.

    A failure here is a failure of the demonstration, not of the
    demonstration's environment: it exits non-zero because a ``check()``
    raised, and the assertion prints the whole of its output so the failing
    claim is the first thing a reader sees.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for step in STEPS:
        assert step in output, f"the demonstration never reached the step {step!r}"

    checks = [line for line in output.splitlines() if line.strip().startswith("[ok]")]
    assert checks, "the demonstration printed no checks at all"
    assert len(checks) >= MINIMUM_CHECKS, (
        f"the demonstration made only {len(checks)} check(s); at least "
        f"{MINIMUM_CHECKS} were expected, so a claim was removed"
    )
    assert f"{len(checks)} checks passed." in output, (
        "the demonstration's own count of its checks does not match the number "
        "it printed, so its summary is not a fact about the run"
    )


@pytest.mark.e2e
def test_the_two_surfaces_were_compared_against_one_store(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The CLI's task state and the API's task document were compared, field by field.

    The comparison is the gate's exit test, and what makes it evidence is the
    *number of fields*: a comparison of two empty documents would also say
    "no differences", so the count is what says the comparison happened over
    the task and not over nothing.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    compared = re.search(r"compared\s+:\s+(\d+) field\(s\), (\d+) differing", output)
    assert compared is not None, "the demonstration never reported a field-by-field comparison"
    assert int(compared.group(1)) > 100, (
        f"only {compared.group(1)} field(s) were compared; the task document has "
        "far more than that, so the comparison was over too little"
    )
    assert compared.group(2) == "0", (
        f"{compared.group(2)} field(s) differed between the CLI's task state and the "
        "API's task document"
    )


@pytest.mark.e2e
def test_the_report_bytes_were_compared_by_hash(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """Each of the four forms was compared as stored against as served.

    The hash is the comparison: the file the report operation wrote and the
    bytes the API serves are the same bytes, for each of the four forms. A
    comparison against a *re-render* would also be a hash comparison, and
    would prove something else -- so the demonstration names the stored file.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for form in ("report.md", "report.html", "report.docx", "report.pdf"):
        assert f"the {form} the CLI names is the bytes the API serves" in output, (
            f"the demonstration never compared the {form} as stored against as served"
        )


@pytest.mark.e2e
def test_the_material_was_ingested_through_the_cli(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration put the material in the ledger through the CLI.

    A demonstration that called the material module directly would still
    work, and would still print its "ok" lines; what it would not be is a
    demonstration of the surfaces agreeing. So the two lines that say the CLI
    did it are asserted here.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "the task holds the material the CLI was told about" in output, (
        "the demonstration did not bind the material through the CLI"
    )
    assert "the CLI can report the material it ingested" in output, (
        "the demonstration did not report the material through the CLI"
    )


@pytest.mark.e2e
def test_every_comparison_was_shown_a_difference_it_had_to_find(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """Each comparison in the demonstration can fail, and this is the evidence.

    A comparison that compares nothing also reports "no differences", so a
    demonstration whose comparisons had been narrowed would still print its
    "ok" lines and still pass the test above. The demonstration therefore runs
    each comparison once over something that must answer the other way, and
    insists it finds the difference.

    **This test reads the demonstration's output for that evidence**, because
    a control inside the demonstration that the test cannot see is the same
    defect one level down.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for control in (
        "the field-by-field comparison finds the difference it was given",
        "the byte comparison finds the difference it was given",
        "the refusal comparison finds the difference it was given",
        "the refusal comparison tells this refusal from another",
        "the staleness comparison finds the difference it was given",
        "the staleness comparison says no about a receipt the walk did not mark",
        "the changed-hash comparison finds the difference it was given",
        "the staleness walk says nothing is stale while the material is unchanged",
    ):
        assert control in output, (
            f"the demonstration never ran the control {control!r}, so its comparison "
            "cannot be told from one that compares nothing"
        )

    # And the evidence itself: the planted difference was found, and it was
    # one field.
    planted = re.search(r"control\s+:\s+(\d+) field\(s\) differ in the altered copy", output)
    assert planted is not None, "the demonstration never reported the control's finding"
    assert int(planted.group(1)) == 1, (
        f"the control found {planted.group(1)} difference(s) in the altered copy; "
        "exactly one was planted"
    )

    # The refusal requirement, over the two grant requests: the service
    # refused one of them, and it was the second. A demonstration that only
    # said "the second was refused" would not say how many were refused.
    refused = re.search(r"the service refused: \[(.+)\]", output)
    assert refused is not None, "the demonstration never reported which grant requests were refused"
    assert refused.group(1) == "'repeated'", (
        f"the demonstration reported that the service refused {refused.group(1)}; "
        "the repeated grant is the only one of the two that should be refused"
    )


@pytest.mark.e2e
def test_the_report_carries_a_claim_cited_to_the_ingested_material(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The report carries a claim, and the claim rests on the ingested material.

    A claim rests on a cited record, and a citation points into material the
    task holds. The task holds the material because the CLI ingested it, so
    the report is not carrying disclosures only.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "the report carries the claim, and cites the address it rests on" in output, (
        "the demonstration's report carried no claim"
    )
    claims = re.search(r"claims\s+:\s+(\d+)", output)
    assert claims is not None, "the demonstration never reported how many claims it carried"
    assert int(claims.group(1)) >= 1, "the demonstration's report carried no claim"


@pytest.mark.e2e
def test_the_refusals_were_refusals_with_a_reason(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """A foreign origin, a missing token and a spent approval were each refused.

    Asserted on the reasons rather than on the messages, because a reason is
    a closed vocabulary: ``origin_refused`` and ``session_required`` are
    different facts, and a demonstration that printed the same word for both
    would pass a test that looked at the prose.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "origin_refused" in output, "a request from another origin was not refused"
    assert "session_required" in output, "a mutation without the token was not refused"
    assert "approval_refused" in output, "the same grant was applied twice"


@pytest.mark.e2e
def test_the_staleness_came_from_the_repositorys_own_walk(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The report was marked stale by the repository's walk, with its own reason.

    The reason is the repository's constant, imported here and compared: a
    demonstration that composed its own sentence would still say something was
    stale, and the reason for believing it is that the sentence is the
    repository's.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert STALE_REASON in output, (
        "the demonstration did not record the repository's own staleness reason"
    )
    assert "the repository's own walk marked the report stale" in output, (
        "the demonstration did not use the repository's walk"
    )


@pytest.mark.e2e
def test_the_demonstration_says_what_it_did_not_exercise(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The two known limits were named in the demonstration's own output.

    The event stream is not consumed by the workbench, and the workbench
    cannot switch the selected project. A demonstration that quietly passed
    over both would read as a demonstration of something it is not.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "What this did not exercise" in output, (
        "the demonstration did not say what it did not exercise"
    )
    assert "event stream" in output, "the event stream's absence was not named"
    assert "switch the selected project" in output, (
        "the inability to switch the selected project was not named"
    )


@pytest.mark.e2e
def test_the_demonstrations_workspace_is_outside_the_repository(
    demonstration: subprocess.CompletedProcess[str],
    repo_root: Path,
) -> None:
    """The workspace the demonstration made is not inside the checkout.

    A workspace inside the repository would make the run depend on the tree it
    runs in -- and would leave the checkout dirty, which is what "a clean
    clone" is about.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr

    made = re.search(r"workspace\s+:\s+(\S+)", demonstration.stdout)
    assert made is not None, "the demonstration never said which workspace it made"
    workspace = Path(made.group(1))
    assert not workspace.is_relative_to(repo_root), (
        f"the demonstration's workspace {workspace} is inside the repository {repo_root}"
    )


@pytest.mark.integration
def test_the_cli_and_the_api_agree_about_the_task(tmp_workspace: Path) -> None:
    """The two surfaces' task documents are the same, read by the test itself.

    The demonstration compares them too, but a comparison made inside the
    demonstration is a comparison the demonstration could get wrong -- narrowed
    to one field, or made against a document it derived in-process rather
    than one the service served. This one is made by the test, which asks each
    surface and compares what comes back, so a product in which the CLI and
    the API disagree fails here even so.

    **Field by field, and the difference is named.** A comparison that said
    only "they differ" would not say what differed, and a comparison that
    said "they agree" over two empty documents would agree about nothing.
    """
    assert run_cli(tmp_workspace, "init").returncode == 0
    created = run_cli(
        tmp_workspace,
        "task",
        "create",
        "--title",
        "Two surfaces, one task",
        "--objective",
        "See that both say the same thing.",
        "--criterion",
        "Field for field.",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    task_id = TaskId(json.loads(created.stdout)["task_id"])

    cli = run_cli(tmp_workspace, "task", "status", "--json")
    assert cli.returncode == 0, cli.stderr
    cli_state: dict[str, Any] = json.loads(cli.stdout)

    location = locate(tmp_workspace)
    config = read_config(location)
    with (
        application_context(location, config, task_id) as context,
        TestClient(create_app(context)) as client,
    ):
        api_state: dict[str, Any] = client.get("/task").json()

    cli_leaves = _leaves(cli_state)
    api_leaves = _leaves(api_state)
    differing = sorted(
        name
        for name in set(cli_leaves) | set(api_leaves)
        if cli_leaves.get(name) != api_leaves.get(name)
    )
    assert len(cli_leaves) >= 8, (
        f"only {len(cli_leaves)} field(s) were compared; a task document carries "
        "more than that, so the comparison was over too little"
    )
    assert str(task_id) in cli_leaves.values(), (
        "the comparison did not cover the task's own identity, so it was not a "
        "comparison of two documents about this task"
    )
    assert not differing, (
        f"{len(differing)} field(s) differ between the CLI's task state and the "
        f"API's task document: {differing}"
    )


def _leaves(document: Any, path: str = "") -> dict[str, Any]:
    """Every leaf of a document, by the path that names it."""
    if isinstance(document, Mapping):
        found: dict[str, Any] = {}
        for key, value in document.items():
            found.update(_leaves(value, f"{path}.{key}"))
        return found
    if isinstance(document, list):
        found = {}
        for index, value in enumerate(document):
            found.update(_leaves(value, f"{path}[{index}]"))
        return found
    return {path: document}
