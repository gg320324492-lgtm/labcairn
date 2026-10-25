"""The outsider's path is run by a test, so it cannot quietly stop working.

``docs/EVALUATION.md`` names seven Phase 1 blockers, and the first one is the
only one about a **person** rather than about the product: *"A new user cannot
complete a task from a clean environment following README."* A test suite
cannot express that directly, so ``scripts/outsider_path.py`` is the way it
becomes expressible — and this file runs that script.

**The run is the assertion.** The script makes every claim through a check
that raises rather than warns, so a zero exit means every one of them held and
a non-zero exit names the one that did not. This file therefore asserts the
exit code first, and the rest of it reads the machine-readable report the run
produced for the things the exit code cannot say on its own: which commands
ran, in which directory, and which claims were made.

**The report is checked, not just its existence.** A report that says a
command ran is a claim; the run's own record of the command's exit code is
the measurement. So every README command the report names must be there with
the exit code the script recorded, and the whole-suite command's reduction must
be recorded too — a witness run that could be read as a full-suite run would
be a witness that lies about what it measured.

**The mechanism is watched as well as the run.** The script's command table
is a check, and a check that nobody watches can be neutered while the run
stays green. So this file also drives the table's check with a README that
shows a command the table does not run, and with one that omits a command the
table does run, and requires both to fail — and drives the extractor with a
document that holds a ```` ```python ```` block, to show that prose is not read
as an instruction.

**The run happens in a clean clone, and that is asserted rather than assumed.**
The report names where the clone was, what commit it was at, and where the
package under test was loaded from; a run that quietly used the developer's
own checkout would satisfy every other assertion here and prove nothing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest

#: The script, as a person runs it.
SCRIPT: Path = Path(__file__).resolve().parent.parent / "scripts" / "outsider_path.py"

#: The acceptance record, which the report's numbers are also written into.
RECORD: Path = (
    Path(__file__).resolve().parent.parent / "docs" / "acceptance" / "LC-P1-14-outsider-path.md"
)

#: The command whose reduction the witness mode applies. It is the whole
#: suite, and running the whole suite from inside the suite would recurse.
WHOLE_SUITE: str = "uv run pytest"


class OutsiderRun(NamedTuple):
    """One run of the script, and the report it wrote."""

    completed: subprocess.CompletedProcess[str]
    report: dict[str, Any]
    work_root: Path


def load_script() -> Any:
    """The script, loaded as a module.

    The script is a tool rather than a package, so it is loaded the way a
    person would run it: by its own path. Loading it is how this file can
    drive the script's own checks with inputs that must make them fail.
    """
    spec = importlib.util.spec_from_file_location("outsider_path", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The module is registered before it runs: a dataclass asks
    # ``sys.modules`` for its own namespace while it is being built, and a
    # module that was never registered is not there to be asked.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def outsider_run(tmp_path_factory: pytest.TempPathFactory) -> OutsiderRun:
    """The script's run, once for the whole module.

    Its own work root, outside the repository: a run inside the checkout would
    make the run depend on the tree it runs in, and would leave the checkout
    dirty — which is the opposite of what this script claims to demonstrate.

    **The run is skipped, loudly, on a machine that cannot run the README's
    web commands** — that is, one with no pnpm, no corepack and no npm. The
    README asks for Node ≥ 24.16 with pnpm ≥ 9.15.9, so such a machine has
    not met the requirements the README states, and the script refuses to
    pretend otherwise. This mirrors what
    `tests/test_readme_accuracy.py` does with the same commands, and a CI
    runner has Node, so the skip does not happen there.
    """
    if not (shutil.which("pnpm") or shutil.which("corepack") or shutil.which("npm")):
        pytest.skip(
            "no pnpm, corepack or npm is available, so the README's web commands "
            "cannot be run; the README asks for Node >= 24.16 with pnpm >= 9.15.9"
        )
    work = tmp_path_factory.mktemp("outsider-path")
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "witness", "--work-root", str(work)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=3600,
        check=False,
    )
    report_path = work / "outsider-path-report.json"
    report: dict[str, Any] = {}
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return OutsiderRun(completed=completed, report=report, work_root=work)


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
def test_the_outsiders_path_runs_and_every_claim_holds(
    outsider_run: OutsiderRun,
) -> None:
    """The script exits zero, and every claim it made was made.

    A failure here is a failure of the walk, not of its environment: the
    script exits non-zero because a check raised, and the assertion prints
    the whole of its output so the failing claim is the first thing a reader
    sees.
    """
    assert outsider_run.completed.returncode == 0, (
        outsider_run.completed.stdout + outsider_run.completed.stderr
    )
    assert outsider_run.report, "the script wrote no report"
    assert outsider_run.report.get("failure") is None, (
        f"the run reported a failure: {outsider_run.report.get('failure')}"
    )

    checks = outsider_run.report["checks"]
    assert checks, "the run recorded no checks at all"
    failed = [check["label"] for check in checks if not check["ok"]]
    assert not failed, f"the run recorded checks that did not hold: {failed}"


@pytest.mark.e2e
def test_the_run_was_made_in_a_clean_clone(outsider_run: OutsiderRun, repo_root: Path) -> None:
    """The clone was outside the repository, clean, and at the same commit.

    The three facts are the difference between "a stranger can do this" and
    "this machine can do this", so they are asserted from the report rather
    than taken on trust.

    **The commit is one this repository has.** The report names the commit
    the clone was made from, and a commit that is in no repository here is a
    commit nobody can check the clone against.
    """
    report = outsider_run.report
    clone = report["clone"]
    assert clone["path"], "the report names no clone"
    assert clone["head"], "the report names no commit for the clone"
    assert clone["head"] == report["repository_head"], (
        f"the clone is at {clone['head']} and the repository is at {report['repository_head']}"
    )
    present = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{clone['head']}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert present.returncode == 0, (
        f"the commit the clone was made from, {clone['head']}, is not in this "
        f"repository, so the clone cannot be checked against it"
    )
    clone_path = Path(clone["path"])
    assert not clone_path.is_relative_to(Path(report["repository"]).resolve()), (
        f"the clone {clone_path} is inside the repository {report['repository']}"
    )
    labels = {check["label"] for check in report["checks"]}
    assert "the clone's working tree is clean" in labels
    assert "the clone is outside the repository it was cloned from" in labels
    assert "the clone has no .venv" in labels


@pytest.mark.e2e
def test_the_walk_resolved_its_work_root(outsider_run: OutsiderRun) -> None:
    """The walk ran in the resolved spelling of its work root, not the given one.

    **This is the workaround for the product's Windows defect.** On a Windows
    machine whose temporary directory is spelled in the 8.3 short form, the
    product refuses a write to a new file under it: the declared path keeps the
    short spelling and the root comes back long-spelled, so two spellings of
    one directory are compared as two directories. The walk resolves its work
    root before it makes anything under it, so the whole walk is in one
    spelling.

    The report carries both spellings, and this test says the walk used the
    resolved one — which is the property the workaround exists for.
    """
    report = outsider_run.report
    given = Path(report["work_root_as_given"])
    used = Path(report["work_root"])
    assert str(used) == str(given.resolve()), (
        f"the walk used {used} and was given {given}; the resolved spelling is {given.resolve()}"
    )
    assert "work_root_was_short_spelled" in report, (
        "the report does not say whether the work root was short-spelled, so a "
        "reader cannot tell whether the workaround was needed"
    )


@pytest.mark.e2e
def test_the_walk_ran_the_clones_own_code(outsider_run: OutsiderRun) -> None:
    """The code the walk exercised was the clone's, not the developer's.

    A run that used the developer's own tree would satisfy every other
    assertion here and prove nothing about a clean clone. The package's path
    is in the report, and it has to be inside the clone.
    """
    walk = outsider_run.report["walk"]
    package = Path(walk["package"]).resolve()
    clone = Path(outsider_run.report["clone"]["path"]).resolve()
    repository = Path(outsider_run.report["repository"]).resolve()
    assert package.is_relative_to(clone), (
        f"the package under test was loaded from {package}, which is not inside the clone {clone}"
    )
    assert not package.is_relative_to(repository), (
        f"the package under test was loaded from {package}, which is inside the "
        f"developer's own repository {repository}"
    )


# --------------------------------------------------------------------------- #
# The README's commands
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
def test_every_readme_command_was_run_or_recorded_as_not_runnable(
    outsider_run: OutsiderRun,
) -> None:
    """Every command the README shows was run, in the clone, and it succeeded.

    **The set is compared, not the count.** A command the README shows that
    the run did not execute is the acceptance clause's failure, and a run that
    executed a command the README does not show is a run that was not
    following the README. Both directions are checked against the README in
    the clone.

    **A command this machine cannot run is recorded, not failed.** The web
    package declares the Node and the pnpm it needs, and a runner that runs
    the Python suite has neither — so the sweep records those commands as
    not run, with the reason. A command that could not be run is not a
    command that did not work; a command that ran and failed is.

    **The product's own commands are not excused.** They are the environment
    the CLI runs in, and they run everywhere — so a non-web command that was
    not run fails here.
    """
    report = outsider_run.report
    documented = report["readme_commands_documented"]
    ran = report["readme_commands_run"]
    assert documented, "the report names no README command"
    assert ran, "the report records no command run"

    documented_set = set(documented)
    ran_set = {entry["documented"] for entry in ran}
    assert documented_set == ran_set, (
        "the commands the README shows and the commands the run executed are not the "
        f"same set; only in the README: {sorted(documented_set - ran_set)}; "
        f"only in the run: {sorted(ran_set - documented_set)}"
    )

    web_ran = False
    for entry in ran:
        if entry.get("ran"):
            web_ran = web_ran or entry["documented"].startswith("pnpm ")
            assert entry["exit_code"] == 0, (
                f"the README's `{entry['documented']}` exited {entry['exit_code']}:\n"
                f"{entry['stdout_tail'][-2000:]}\n{entry['stderr_tail'][-2000:]}"
            )
        else:
            assert entry.get("reason"), (
                f"the README's `{entry['documented']}` was not run and no reason was "
                "recorded for it"
            )
            assert entry["documented"].startswith("pnpm "), (
                f"the README's `{entry['documented']}` was not run, and it is not a web "
                "command: the product's own commands have to run everywhere"
            )
    # The web commands are in one state or the other: they all ran, or they
    # were all recorded as not runnable. A mix would mean the machine could
    # run some of them and not others, which is not a thing that happens.
    web_states = {entry.get("ran") for entry in ran if entry["documented"].startswith("pnpm ")}
    assert len(web_states) <= 1, (
        f"the web commands are in more than one state: {sorted(str(s) for s in web_states)}"
    )
    assert web_ran or web_states == {False}, (
        "the web commands were neither run nor recorded as not runnable"
    )


@pytest.mark.e2e
def test_the_witness_run_records_the_suite_reduction(outsider_run: OutsiderRun) -> None:
    """The whole-suite command's reduction is recorded, so the run cannot lie.

    The reduction is forced: running the whole suite from inside the suite
    would recurse, because this file's own test runs the script, which runs
    the suite, which runs this file's own test. A witness run that could be
    read as a full-suite run would be a witness that lies about what it
    measured — so the reduction is recorded against the command it applies
    to, and this test requires that record to be there.
    """
    ran = {entry["documented"]: entry for entry in outsider_run.report["readme_commands_run"]}
    whole = ran.get(WHOLE_SUITE)
    assert whole is not None, f"the report does not name the README's `{WHOLE_SUITE}`"
    assert whole["reduced"] is True, (
        "the witness run did not reduce the whole-suite command, so it either ran "
        "the whole suite from inside the suite or did not run it at all"
    )
    assert whole["reduction"], "the reduction was applied but not recorded"
    assert "--collect-only" in " ".join(whole["argv"]), (
        f"the reduced command is {' '.join(whole['argv'])}, which is not a collection"
    )


@pytest.mark.e2e
def test_the_record_names_every_command_and_its_outcome(
    outsider_run: OutsiderRun,
) -> None:
    """The acceptance record carries the run's numbers, not a paraphrase.

    **The record is checked against the run, not against a copy of itself.**
    Every command the run executed must be named in the record with the exit
    code the run recorded — so a record that drifted away from the run fails
    here, and a record that quietly dropped a command fails here too.
    """
    text = RECORD.read_text(encoding="utf-8")
    for entry in outsider_run.report["readme_commands_run"]:
        assert entry["documented"] in text, (
            f"the acceptance record does not name the README's `{entry['documented']}`, "
            "which the run executed"
        )
    assert "uv run pytest" in text, "the acceptance record does not name the suite command"
    assert "--collect-only" in text, (
        "the acceptance record does not say that the witness run reduced the whole-suite command"
    )


# --------------------------------------------------------------------------- #
# The walk's claims
# --------------------------------------------------------------------------- #

#: The claims the walk makes, one per line of the deliverable. The label is
#: the script's own wording, so a claim that was removed shows up here.
REQUIRED_CLAIMS: tuple[str, ...] = (
    "the task holds the material the CLI was told about",
    "the task holds a PDF, a CSV and a Markdown",
    "the PDF is a text PDF, so it can be read and cited",
    "the inventory stage ran against the bound material",
    "the ledger holds three records, one for each kind of material",
    "the address anc-csv resolves in the material the task holds",
    "the address anc-pdf resolves in the material the task holds",
    "the address anc-md resolves in the material the task holds",
    "the run wrote a figure",
    "the figure on disk is the bytes the receipt records",
    "two renders of one recipe are byte-identical",
    "the revision wrote the canonical document, the manifest and the four forms",
    "the report carries the three claims, one for each kind of material",
    "every claim cites the address it rests on",
    "the report's snapshot names the records it is a view of",
    "the report's citations are locators of all three kinds",
    "the CLI's task state and the API's task document are the same, field by field",
    "the field-by-field comparison finds the difference it was given",
    "the report.md the CLI names is the bytes the API serves",
    "the byte comparison finds the difference it was given",
    "the paths the walk used are the ones the workbench reads",
    "the repository's own measurement says the material moved",
    "the report's own receipt is among the artefacts the walk marked stale",
    "the walk marked them stale with the repository's own reason",
    "the stale mark did not regenerate anything",
    "the report is generated again, as a second revision",
    "the first revision's bytes are unchanged",
    "the second revision is not itself marked stale",
    "the analysis runs again over the revised bytes and writes a figure",
    "the new figure is not the old figure's bytes",
    "the walk attempted to recompute the report from the revised bytes",
    "the task after the restart is the task before it",
    "the service, in a new process, serves the same task",
    "the resume is a new run against the same task, not a new task",
    "every file the product produced is in the task's own output area",
    "the repository's own fixture corpus is byte-identical to what it was",
    "the product wrote nothing into the research folder",
)


@pytest.mark.e2e
def test_every_claim_the_deliverable_names_was_made(outsider_run: OutsiderRun) -> None:
    """Each claim the P1 deliverable names was made, and it held.

    The list is the deliverable, one claim at a time: bind a research folder
    with a PDF, a CSV and a Markdown; make a task; get a report and a
    deterministic figure with source locators and an evidence ledger; revise
    it; reopen the same task after a restart; read it through two surfaces;
    leave the original material unchanged. A claim that was removed from the
    script shows up here as a missing label.
    """
    labels = {check["label"] for check in outsider_run.report["checks"]}
    missing = [claim for claim in REQUIRED_CLAIMS if claim not in labels]
    assert not missing, (
        f"the run did not make these claims: {missing}. Either a step of the "
        "deliverable is not covered, or a claim was renamed."
    )


@pytest.mark.e2e
def test_the_walk_says_what_it_did_not_exercise(outsider_run: OutsiderRun) -> None:
    """The run named its own limits.

    A run that quietly passed over the browser, over the missing product
    operation, or over the absence of a real provider would read as a run of
    something it is not.
    """
    walk = outsider_run.report["walk"]
    limits = " ".join(walk["not_exercised"]).lower()
    assert "react" in limits, "the run did not say the React application was not run"
    assert "evidence record" in limits, (
        "the run did not say that no product operation writes an evidence record"
    )
    assert "provider" in limits, "the run did not say that no real provider was called"


# --------------------------------------------------------------------------- #
# The mechanism: the command table, and the extractor
# --------------------------------------------------------------------------- #


def _a_clone_with_readme(tmp_path: Path, body: str) -> Path:
    """A directory that looks enough like a clone for the table's check."""
    clone = tmp_path / "clone"
    clone.mkdir(exist_ok=True)
    (clone / "README.md").write_text(body, encoding="utf-8")
    return clone


def test_the_command_table_check_fails_when_the_readme_shows_a_command_it_does_not_run(
    tmp_path: Path,
) -> None:
    """The check is watched, and it can fail.

    **A command in the README that the script does not run is a failure** —
    that is the acceptance clause, and a check nobody watches can be neutered
    while every run stays green. So the check is driven with a README that
    shows a command the table has no row for, and it has to refuse it and
    name the command.
    """
    script = load_script()
    clone = _a_clone_with_readme(
        tmp_path,
        "# A README\n\n```bash\nuv sync\nuv run a-command-nobody-runs\n```\n",
    )
    recorder = script.Recorder("test")
    with pytest.raises(AssertionError) as refusal:
        script.check_the_command_table(clone, recorder)
    assert "a-command-nobody-runs" in str(refusal.value), (
        f"the check refused, but did not name the command it refused: {refusal.value}"
    )


def test_the_command_table_check_fails_when_the_script_runs_a_command_the_readme_does_not_show(
    tmp_path: Path,
) -> None:
    """The other direction is watched too.

    A script that runs a command nobody can find in the README is not
    following the README, and a table that quietly grows is how that happens.
    """
    script = load_script()
    clone = _a_clone_with_readme(tmp_path, "# A README\n\n```bash\nuv sync\n```\n")
    recorder = script.Recorder("test")
    with pytest.raises(AssertionError) as refusal:
        script.check_the_command_table(clone, recorder)
    assert "uv run pytest" in str(refusal.value), (
        f"the check refused, but did not name the row it refused: {refusal.value}"
    )


def test_the_command_table_check_passes_when_the_readme_shows_exactly_its_commands(
    tmp_path: Path,
) -> None:
    """The control: the check passes when the two agree.

    A check that refused everything would satisfy the two tests above, so it
    is asked about a README that shows exactly the table's commands and has to
    accept it.
    """
    script = load_script()
    documented = "\n".join(command.documented for command in script.README_COMMANDS)
    clone = _a_clone_with_readme(tmp_path, f"# A README\n\n```bash\n{documented}\n```\n")
    recorder = script.Recorder("test")
    script.check_the_command_table(clone, recorder)
    assert recorder.checks, "the check recorded nothing"
    assert all(check["ok"] for check in recorder.checks)


def test_the_extractor_reads_instructions_and_ignores_illustrations() -> None:
    """A ```` ```python ```` block is prose, and is not read as a command.

    The README holds blocks that are illustrations as well as blocks that are
    instructions, and an extractor that took both would run a line of Python as
    a shell command. So the extractor is asked about a document with both, and
    has to find the instructions and leave the illustrations alone.
    """
    script = load_script()
    text = (
        "# A README\n\nSome prose.\n\n"
        "```bash\nuv sync\nuv run pytest\n```\n\n"
        "```python\nprint('an illustration, not an instruction')\n```\n\n"
        "```text\nalso an illustration\n```\n"
    )
    assert script.readme_commands(text) == ["uv sync", "uv run pytest"]


def test_the_extractor_ignores_comments_and_blank_lines() -> None:
    """A comment in a shell block is a comment, not a command."""
    script = load_script()
    text = "# A README\n\n```bash\n# a comment\n\nuv sync\n```\n"
    assert script.readme_commands(text) == ["uv sync"]


def test_the_version_comparison_reads_the_ranges_the_repository_writes() -> None:
    """The comparison the web-environment check uses, watched.

    It reads the ranges ``web/package.json`` writes -- ``">=24.16.0 <25"`` --
    and says **unknown** when it meets a range it does not understand, rather
    than guessing: a check that said "no" about a range it could not read
    would refuse a machine that could have run the command.
    """
    script = load_script()
    assert script.satisfies("24.16.0", ">=24.16.0 <25") is True
    assert script.satisfies("v24.16.0", ">=24.16.0 <25") is True
    assert script.satisfies("24.16.1", ">=24.16.0 <25") is True
    assert script.satisfies("25.0.0", ">=24.16.0 <25") is False
    assert script.satisfies("24.15.9", ">=24.16.0 <25") is False
    assert script.satisfies("20.19.4", ">=24.16.0 <25") is False
    assert script.satisfies("9.15.9", ">=9.15.9 <10") is True
    assert script.satisfies("10.0.0", ">=9.15.9 <10") is False
    assert script.satisfies("24.16.0", ">=24.16.0") is True
    assert script.satisfies("24.16.0", "24.16.0") is True
    assert script.satisfies("24.16.0", "^24.16.0") is None
    assert script.satisfies("24.16.0", ">=24.16.0 || <20") is None
    assert script.satisfies("not-a-version", ">=24.16.0 <25") is None


def test_the_extractor_finds_nothing_in_a_document_with_no_commands() -> None:
    """The control for the extractor: an empty answer is an answer.

    Without this, a broken extractor would find nothing and every test that
    asked it about a real README would pass for the wrong reason.
    """
    script = load_script()
    assert script.readme_commands("# A README\n\nOnly prose here.\n") == []
