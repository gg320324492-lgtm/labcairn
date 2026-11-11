"""The shell's Node witnesses are run by CI, and that is watched here.

**The property.** `.github/workflows/shell.yml` exists, its `shell-test` job
runs every `*.test.mjs` under `shell/test/`, the job's name carries the matrix
leg so branch protection can tell the platform legs apart, and the job carries
the two things `drain-witness.test.mjs` needs to run at all: the `labcairn`
console script and a scratch directory the runner actually has.

**Why it needs watching.** `pyproject.toml`'s `norecursedirs` names `shell` —
"Electron tree; its Node witnesses are not pytest files" — so no shard, no gate
class and no witness ledger can see the shell's Node cases (44 across eight
files, measured at `CASE_FLOORS_MEASURED_AT`). Before this file,
deleting `shell/test/window-security.test.mjs` left **every** pytest test green,
and renaming a job so that its two platform legs report one name left every
pytest test green too. The dependency-surface audit found the first gap; the CI
deviation list's D2 found the second. This file is the witness for both, and it
is a pytest file, so `scripts/witness_ledger.py` counts it — the Node cases
stay out of the ledger by contract (their count is watched here instead).

**What this file deliberately does not do.** It does not assert that GitHub
*requires* `shell-test (…)` — branch protection is configured outside the
repository and no file here can make a check required. It does not re-assert
the C-1 rule (no `paths:` filter on a `pull_request` trigger): that is watched
by `tests/test_no_reference_leakage.py::test_no_workflow_filters_pull_request_at_all`
over every workflow file, and a second weaker copy of a gate is the thing this
project's rules say not to write.

**The counts are a floor with an anchor, not a hard equality.** A hard
`== <total>` would make every legitimate new Node case an edit to this file. The
recorded per-file floors are what a `node --test` run printed at the commit named below,
and `shell/test/dependency-surface.test.mjs:114` is the in-repo precedent for
what to do when a floor is crossed: *re-measure and update the record, do not
edit the list from memory*.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml
from workflow_job_names import UnrenderableJobNameError, load_workflows, rendered_job_names

#: The workflow the shell's Node witnesses are supposed to live in.
SHELL_WORKFLOW: Final[Path] = Path(".github") / "workflows" / "shell.yml"

#: The job key, and the name it must report. The name carries the matrix axis
#: for the same reason `python-quality` does: two legs sharing a name are one
#: check as far as branch protection is concerned.
SHELL_JOB_KEY: Final[str] = "shell-test"
SHELL_JOB_NAME: Final[str] = "shell-test (${{ matrix.os }})"

#: The platforms the job must run on. This is not decoration: the drain
#: witness's `forceTree` helper has a Windows arm (`taskkill /T /F`,
#: drain-witness.test.mjs:172) and a non-Windows arm (`SIGKILL`, :178), and a
#: single-platform job runs one of them in CI never.
SHELL_PLATFORMS: Final[tuple[str, ...]] = ("windows-latest", "ubuntu-latest")

#: The directory the CI command must cover.
SHELL_TEST_DIR: Final[str] = "shell/test"

#: The top-level Node case declaration. `node --test` runs the cases this file
#: calls at the top level of a test file; a call indented inside `describe()`
#: is counted by Node too, but it is not what the recorded floors below counted,
#: so the anchor is the line-start form and the synthetic check below holds it.
NODE_CASE: Final[re.Pattern[str]] = re.compile(r"(?m)^(?:test|it)\(")

#: The per-file Node case counts, and the commit they were measured at.
#: The six original files were measured with
#: `node --test --test-reporter=spec` on Node v24.16.0 at
#: `9dee4ed6a9e4e00a92f28d792a7b72f3e1a16d92` — 27 cases, 27 pass, 0 fail.
#: `packaging-config.test.mjs` arrived with T08; its four cases were measured
#: from the combined tree at `6cdbfb56ce29dd19e4f56dae549b4d476d998d1e`.
#: `notice-licences.test.mjs` arrived with the full NOTICE surface; its seven
#: cases were measured from the final branch tree at
#: `f0f55929a35ffb59b682c289045eef26aaeb99dc`, whose `shell/test/` tree is
#: identical to the merged tree. The eight files together declare 44 cases;
#: `node --test` measured 44 pass, 0 fail on Node v24.16.0 after the packaged
#: bundle's own directory was derived, at
#: `8b26002f5cfb9625d36b868de08bd00b0341bb11`. The five cases the guard adds are its own: the
#: configuration names it; it is shaped the way electron-builder resolves a
#: hook; the hook it calls throws on a missing bundle and returns true on a
#: good one; and the script form refuses a missing bundle and accepts a
#: complete one.
#: A development-machine count of *what the files declare*, not of duration:
#: the job's runner cost is recorded separately, after its first runner run.
SHELL_CASE_FLOORS: Final[dict[str, int]] = {
    "config.test.mjs": 5,
    "dependency-surface.test.mjs": 3,
    "drain-witness.test.mjs": 5,
    "live-guard.test.mjs": 5,
    "native-surface.test.mjs": 6,
    "notice-licences.test.mjs": 7,
    "packaging-config.test.mjs": 9,
    "window-security.test.mjs": 4,
}
CASE_FLOORS_MEASURED_AT: Final[str] = "8b26002f5cfb9625d36b868de08bd00b0341bb11"


# --------------------------------------------------------------------------
# Readers. Each one is a function rather than inline assertions so the synthetic
# checks at the end of this file can show that it fails for the property — a
# coverage check nobody can test is a coverage check that can be turned off.
# --------------------------------------------------------------------------


def _workflow_document(repo_root: Path) -> dict[Any, Any]:
    path = repo_root / SHELL_WORKFLOW
    assert path.is_file(), (
        f"{SHELL_WORKFLOW} is not there. The shell's Node witnesses are excluded "
        "from pytest by `norecursedirs`, so without this workflow CI never runs them."
    )
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{SHELL_WORKFLOW} is not a workflow mapping"
    # `dict[Any, Any]`, not `dict[str, Any]`: PyYAML reads YAML 1.1's bare `on`
    # as the boolean True, so a workflow document really does carry a key that
    # is not a string. `test_ci_shard_coverage.py` notes the same quirk.
    return document


def _triggers(document: dict[Any, Any]) -> dict[str, Any]:
    """The workflow's trigger mapping, whichever key PyYAML stored it under."""
    raw = document.get("on", document.get(True))
    assert isinstance(raw, dict), "the workflow declares no trigger mapping"
    return raw


def _shell_job(document: dict[Any, Any]) -> dict[str, Any]:
    jobs = document.get("jobs")
    assert isinstance(jobs, dict), "shell.yml declares no jobs"
    assert SHELL_JOB_KEY in jobs, (
        f"shell.yml has no job keyed {SHELL_JOB_KEY!r}, so the name this file "
        "records is not the name CI reports"
    )
    job = jobs[SHELL_JOB_KEY]
    assert isinstance(job, dict), f"shell.yml's {SHELL_JOB_KEY} job is not a mapping"
    return job


def _run_steps(job: dict[str, Any]) -> list[str]:
    """The `run:` commands of a job, in order."""
    return [str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict)]


def _test_commands(job: dict[str, Any]) -> list[str]:
    """The steps that invoke `node --test`."""
    return [command for command in _run_steps(job) if "node --test" in command]


def _shell_test_files(repo_root: Path) -> list[str]:
    """Every Node test file under `shell/test/`, as `/`-separated paths.

    Normalised to forward slashes on purpose: the CI command quotes
    `test/*.test.mjs`, and a comparison that used Windows' separator would call
    the glob a non-match on the platform that most needs the witness.
    """
    directory = repo_root / "shell" / "test"
    assert directory.is_dir(), f"{SHELL_TEST_DIR} is not a directory"
    files = [
        path.relative_to(repo_root / "shell").as_posix() for path in directory.rglob("*.test.mjs")
    ]
    assert files, f"{SHELL_TEST_DIR} holds no *.test.mjs file, so there is nothing to cover"
    return sorted(files)


def _pattern_matches(pattern: str, name: str) -> bool:
    """Whether a `node --test` glob covers one file.

    Written out rather than handed to `fnmatch`, because `fnmatch`'s `*` matches
    across `/` while Node's `--test` glob does not: `test/*.test.mjs` covers
    `test/config.test.mjs` and **not** `test/nested/x.test.mjs`, which needs
    `test/**`. A coverage check built on `fnmatch` would report a nested witness
    as run by a glob that never reaches it — a green that hides an unrun test,
    which is the failure this file exists to close.
    """
    pattern_parts = pattern.split("/")
    name_parts = name.split("/")

    def match(pattern_index: int, name_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return name_index == len(name_parts)
        segment = pattern_parts[pattern_index]
        if segment == "**":
            return any(
                match(pattern_index + 1, taken) for taken in range(name_index, len(name_parts) + 1)
            )
        if name_index >= len(name_parts):
            return False
        return fnmatch.fnmatchcase(name_parts[name_index], segment) and match(
            pattern_index + 1, name_index + 1
        )

    return match(0, 0)


def _files_the_command_runs(command: str, all_files: list[str]) -> list[str]:
    """Which of `all_files` a `node --test` command would actually run.

    A command may name files one by one, or hand Node a pattern (Node >= 22
    expands the `--test` pattern itself, which is what makes the same command
    work under a shell that does not expand globs). Both shapes are resolved
    against the same file list, so a command that silently names three of six
    files is reported as running three.
    """
    run: list[str] = []
    for name in all_files:
        for token in re.split(r"[\s'\"]+", command):
            if not token or token.startswith("-"):
                continue
            if token == name or _pattern_matches(token, name):
                run.append(name)
                break
    return run


def _missing_from_commands(commands: list[str], all_files: list[str]) -> list[str]:
    """The files no command in the job runs — the union across commands.

    The union, not "the best single command": a job may legitimately split the
    files over two steps, and each half covered by a different step is fully
    covered. Reading the best single command instead would report the half the
    other step runs as uncovered, and a check that cries wolf gets ignored.
    """
    covered: set[str] = set()
    for command in commands:
        covered.update(_files_the_command_runs(command, all_files))
    return sorted(set(all_files) - covered)


def _node_case_count(text: str) -> int:
    """How many top-level Node cases a test file declares."""
    return len(NODE_CASE.findall(text))


#: The import specifiers a shell witness may name: Node's own built-ins, files
#: under `shell/`, and the repository's own CI tooling under `.github/` (which is
#: where `NOTICE` §5.3's lead command lives, and `notice-licences.test.mjs`
#: imports it rather than copying it). Anything else is a bare specifier, and a
#: bare specifier is a package — the thing the job deliberately does not install.
SHELL_WITNESS_IMPORT_ROOTS: Final[tuple[str, ...]] = ("../", "./", "../../.github/", "../.github/")

#: One `import … from '…'` / `export … from '…'` specifier, static form only.
#: Dynamic `import('x')` is deliberately not matched here; the witness below
#: counts it separately rather than pretending the static read covers it.
NODE_IMPORT: Final[re.Pattern[str]] = re.compile(r"""from\s+'([^']+)'""")
DYNAMIC_IMPORT: Final[re.Pattern[str]] = re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]""")


def _bare_imports(text: str) -> list[str]:
    """Import specifiers that resolve to neither a Node built-in nor a repo file.

    `node:*` is Node's own prefix for a built-in. A relative specifier resolves
    inside the tree. Everything left over — `electron`, `pnpm`, `js-yaml` — is a
    package Node would look for in `node_modules`, and `shell.yml` installs no
    `node_modules`: the job's own comment and the assertion in
    `test_the_test_step_runs_inside_the_shell_and_names_the_runner_temp` both say
    so, and before this reader said it, that comment was the only thing holding it
    up.
    """
    bare: list[str] = []
    for specifier in NODE_IMPORT.findall(text) + DYNAMIC_IMPORT.findall(text):
        # One `startswith` with a flat tuple of prefixes. `SHELL_WITNESS_IMPORT_ROOTS`
        # is itself a tuple, so it is unpacked: nesting it would make the call test a
        # tuple element against a tuple and reject every relative import.
        if specifier.startswith(("node:", *SHELL_WITNESS_IMPORT_ROOTS)):
            continue
        bare.append(specifier)
    return sorted(set(bare))


def _matrix_axes(job: dict[str, Any]) -> dict[str, list[Any]]:
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    assert isinstance(matrix, dict) and matrix, (
        f"shell.yml's {SHELL_JOB_KEY} job has no matrix, so its name names "
        "matrix.os and GitHub cannot render it"
    )
    return {axis: values for axis, values in matrix.items() if axis not in ("include", "exclude")}


# --------------------------------------------------------------------------
# The witnesses
# --------------------------------------------------------------------------


def test_the_shell_workflow_exists_and_runs_on_a_pull_request(repo_root: Path) -> None:
    """A gate that never triggers is a gate that never runs.

    The job must be offered on `pull_request` — the event a required check has
    to satisfy — and on `push` to `main`, so the shell gate is not a workflow
    that only fires by hand. **Whether GitHub requires the name is the owner's
    branch-protection setting**, and no file in this repository can assert it;
    what this can assert is that the workflow offers the trigger a required
    check needs. The C-1 rule that the trigger carries no path filter is
    watched over every workflow file by `test_no_reference_leakage.py`.
    """
    document = _workflow_document(repo_root)
    assert document.get("name") == "shell", (
        f"the workflow's name is {document.get('name')!r}, not `shell`; the "
        f"record and this file name it {SHELL_WORKFLOW}"
    )
    triggers = _triggers(document)
    assert "pull_request" in triggers, "shell.yml does not run on pull_request"

    push = triggers.get("push")
    if isinstance(push, dict):
        assert push.get("branches") == ["main"], (
            f"shell.yml's push trigger is {push.get('branches')!r}; a push to every "
            "branch doubles the legs for no new signal, because a feature "
            "branch's pull_request event already runs this same workflow"
        )
    _shell_job(document)


def test_every_shell_node_witness_is_run_by_the_job(repo_root: Path) -> None:
    """A shell test file CI never runs.

    This is the hole the dependency-surface audit found: the Node witnesses were
    real, they passed, and no CI job invoked them. The property is not "the
    command mentions `shell`" — it is that **each file that exists is a file the
    command runs**.

    **What this reddens, and what it does not.** Narrowing the CI command —
    naming three of the files, dropping the `node --test` step, or moving a
    witness into a subdirectory the `test/*.test.mjs` glob does not cross — makes
    it red. A new file directly under `shell/test/` does **not**: the glob covers
    it, and a docstring claiming otherwise would be a claim this file's own
    witness does not hold. What a new top-level file does trigger is
    `test_every_shell_test_file_is_recorded` below — its name carries no floor
    yet, and the floors are where the Node case counts are watched.
    """
    job = _shell_job(_workflow_document(repo_root))
    commands = _test_commands(job)
    assert commands, (
        f"shell.yml's {SHELL_JOB_KEY} job runs no `node --test` command, so the "
        f"shell witnesses under {SHELL_TEST_DIR} are not run by CI at all"
    )
    all_files = _shell_test_files(repo_root)
    uncovered = _missing_from_commands(commands, all_files)
    assert not uncovered, (
        f"shell.yml's test command does not run these shell test files: {uncovered}. "
        "Either they are named by another step or by another job — or CI never "
        f"runs them, which is what {SHELL_TEST_DIR} being in `norecursedirs` makes silent."
    )


def test_the_test_step_runs_inside_the_shell_and_names_the_runner_temp(repo_root: Path) -> None:
    """The two things `drain-witness.test.mjs` needs that the other files do not.

    `drain-witness.test.mjs` is the one integration file: two of its cases spawn
    the `labcairn` console script (`shell/test/drain-witness.test.mjs:440,462`),
    and `shell/scripts/lib/shell-paths.mjs:29-36` derives that script from the
    checkout's own `.venv` — the project's one-environment rule, and the reason
    a stray `LABCAIRN_SHELL_CLI` would be a lie rather than a fix. So the job
    must run `uv sync --frozen` at the repository root.

    Its scratch default is `E:\\labcairn-local\\shell-test-tmp`
    (`drain-witness.test.mjs:83-87`), a path a GitHub Windows runner has no E:
    volume for and nothing creates. `LABCAIRN_SHELL_TEST_TMP` is the only escape
    hatch, so an env of the runner's temp is load-bearing, not tidiness.

    The step must also run with `working-directory: shell`, because the test
    files import `../src/…` relative to themselves.
    """
    job = _shell_job(_workflow_document(repo_root))
    install_commands = "\n".join(_run_steps(job))
    assert "uv sync --frozen" in install_commands, (
        "shell.yml does not run `uv sync --frozen`, so the checkout has no "
        "`.venv` and the two drain-witness cases that spawn the console script "
        "fail for want of an interpreter rather than for want of a fix"
    )
    assert "pnpm install" not in install_commands, (
        "shell.yml installs the shell's packages. The test files import only "
        "node:* built-ins and files under shell/ or .github/, and the two tests "
        "that concern pnpm-lock.yaml read it as text; installing electron would "
        "add a 100 MB download to a job that never imports it. "
        "test_no_shell_witness_imports_a_package_the_job_does_not_install holds "
        "that claim against the files, not against this sentence."
    )
    for step in job.get("steps", []):
        if not isinstance(step, dict) or "node --test" not in str(step.get("run", "")):
            continue
        defaults = job.get("defaults")
        job_dir = (
            defaults.get("run", {}).get("working-directory") if isinstance(defaults, dict) else None
        )
        working = step.get("working-directory") or job_dir
        assert working == "shell", (
            "the test step does not run with `working-directory: shell`, so the "
            "test files' `../src/…` imports resolve outside the tree they test"
        )
        env = step.get("env")
        assert isinstance(env, dict) and env.get("LABCAIRN_SHELL_TEST_TMP"), (
            "the test step sets no LABCAIRN_SHELL_TEST_TMP, so the drain witness "
            "targets a scratch default the runner does not have"
        )


def test_no_shell_witness_imports_a_package_the_job_does_not_install(repo_root: Path) -> None:
    """`shell.yml` installs no `node_modules`, and that is a claim about the files.

    The job's comment says the shell's test files "import only node:* built-ins
    and files under shell/", and the assertion above refuses a `pnpm install` step.
    Until this reader existed, nothing checked the other half of that arrangement:
    one `import { load } from 'js-yaml'` in one witness would make the job fail on
    every runner for want of a package, and the only local signal would be a
    green `node --test` run on a machine that happens to have the package in some
    parent `node_modules`.

    So the property is read statically, from the files themselves: a specifier
    that is neither a `node:*` built-in nor a path inside the tree is a package,
    and a package is what the job does not install.
    """
    offenders: dict[str, list[str]] = {}
    for name in sorted(SHELL_CASE_FLOORS):
        text = (repo_root / "shell" / "test" / name).read_text(encoding="utf-8")
        bare = _bare_imports(text)
        if bare:
            offenders[name] = bare
    assert not offenders, (
        f"these shell witnesses import a package the shell job does not install: "
        f"{offenders}. Either the job gains a pnpm install step — a ~100 MB "
        "electron download for a job that never imports electron — or the witness "
        "reads what it needs as text, which is what `dependency-surface.test.mjs` "
        "and `notice-licences.test.mjs` do."
    )


def test_the_shell_job_name_carries_the_platform_leg(repo_root: Path) -> None:
    """`shell-test` alone would make the two platform legs one check.

    GitHub identifies a check by its name, so a matrix job whose name does not
    mention the axis is satisfied by whichever leg reports first — and the other
    leg, which then never has to pass, looks like it did. This is the rule
    `python.yml`'s shard names follow and `release.yml`'s comment states; it is
    watched here for the shell job rather than left to a reviewer's eye.
    """
    job = _shell_job(_workflow_document(repo_root))
    name = str(job.get("name", SHELL_JOB_KEY))
    assert name == SHELL_JOB_NAME, f"the shell job's name is {name!r}, not {SHELL_JOB_NAME!r}"
    assert "matrix.os" in name, (
        "the shell job's name does not mention matrix.os, so its two platform "
        "legs report one check name"
    )
    axes = _matrix_axes(job)
    assert "os" in axes, "the shell job's name names matrix.os, which it does not declare"


def test_the_shell_job_spends_both_platform_legs(repo_root: Path) -> None:
    """The legs are the coverage. A leg removed is a witness arm removed.

    The drain witness's group-kill pair has a Windows arm and a Unix arm. Dropping
    either platform does not make the suite cheaper in a way that keeps its
    meaning: it makes one arm of one witness run in CI never. `fail-fast: false`
    is part of the same property — a red Windows leg hidden by a green Ubuntu one
    is the coverage loss in a different shape.
    """
    job = _shell_job(_workflow_document(repo_root))
    axes = _matrix_axes(job)
    assert [str(value) for value in axes["os"]] == list(SHELL_PLATFORMS), (
        f"the shell job's os matrix is {axes['os']!r}; the drain witness's "
        f"Windows and Unix arms need {list(SHELL_PLATFORMS)}"
    )
    strategy = job.get("strategy")
    assert isinstance(strategy, dict) and strategy.get("fail-fast") is False, (
        "the shell job does not set fail-fast: false, so one platform's failure "
        "cancels the other leg and the report says nothing about it"
    )


def test_the_shell_job_name_is_unique_across_every_workflow(repo_root: Path) -> None:
    """A collision between two workflow files is the same deadlock as one inside a file.

    `release-dependency-licences (matrix.os)` was a name its two legs both
    reported, and no test in the repository read `release.yml` at all, so it
    survived every earlier check. The uniqueness read now spans
    `.github/workflows/` and compares **rendered** names — one per matrix leg —
    which is the only version of the check that can see that shape. The same
    read is what keeps a future `shell.yml` job rename from quietly re-merging
    its two legs.
    """
    documents = load_workflows(repo_root / ".github" / "workflows")
    assert documents, ".github/workflows declares no workflows"
    names: list[str] = []
    for path, document in documents:
        names.extend(rendered_job_names(document, path.name))
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, (
        f"these job names are reported by more than one job or matrix leg: {duplicates}"
    )
    shell_names = rendered_job_names(_workflow_document(repo_root), SHELL_WORKFLOW.name)
    assert sorted(shell_names) == sorted(
        f"shell-test ({platform})" for platform in SHELL_PLATFORMS
    ), f"the shell job reports {shell_names}; its legs must be distinguishable checks"


def test_the_shell_case_counts_are_at_least_the_recorded_floors(repo_root: Path) -> None:
    """A Node witness file whose cases were deleted is a witness lost.

    `scripts/witness_ledger.py` counts pytest test functions under `tests/`, so
    the shell's Node cases are invisible to it — correctly, since folding them in
    would change the meaning of every number it has printed. The gap it leaves is
    closed here: each recorded file is asserted to still exist and to still
    declare at least the cases it declared at `CASE_FLOORS_MEASURED_AT`.

    **A floor, not an equality.** Adding a case is normal work; deleting one is
    the thing a composition does quietly. Where a floor is crossed upward, the
    record is re-measured and this table is updated in the same change —
    `shell/test/dependency-surface.test.mjs:114` states the rule in the tree:
    *re-measure, do not edit this list from memory*.
    """
    missing = [
        name for name in SHELL_CASE_FLOORS if not (repo_root / "shell" / "test" / name).is_file()
    ]
    assert not missing, (
        f"these shell test files are gone: {missing}. They carry the witnesses "
        f"recorded at {CASE_FLOORS_MEASURED_AT}; a shell witness that disappears "
        "while every pytest test stays green is the F44 shape in a directory the "
        "ledger cannot read."
    )
    for name, floor in sorted(SHELL_CASE_FLOORS.items()):
        text = (repo_root / "shell" / "test" / name).read_text(encoding="utf-8")
        count = _node_case_count(text)
        assert count >= floor, (
            f"{name} declares {count} top-level Node cases; {floor} were measured "
            f"at {CASE_FLOORS_MEASURED_AT}. Cases were deleted from a shell witness."
        )
    total = sum(
        _node_case_count((repo_root / "shell" / "test" / name).read_text(encoding="utf-8"))
        for name in SHELL_CASE_FLOORS
    )
    assert total >= sum(SHELL_CASE_FLOORS.values()), (
        f"the shell witnesses declare {total} cases between them; "
        f"{sum(SHELL_CASE_FLOORS.values())} were measured at {CASE_FLOORS_MEASURED_AT}"
    )


def test_every_shell_test_file_is_recorded(repo_root: Path) -> None:
    """A shell witness that arrives unrecorded is a witness with no floor.

    The glob in the CI command means a new `shell/test/*.test.mjs` **is** run by
    CI — so the coverage check above stays green for it, correctly. What nothing
    would then watch is its own case count: it would carry no floor, and a later
    composition could delete half its cases with nothing here noticing.

    So every file in the directory must appear in `SHELL_CASE_FLOORS`. Adding a
    shell witness therefore means measuring it and recording it, which is the
    project's rule (*a value that can change is re-measured, not carried
    forward*) applied to the half the ledger cannot read.
    """
    recorded = set(SHELL_CASE_FLOORS)
    present = {path.name for path in (repo_root / "shell" / "test").rglob("*.test.mjs")}
    unrecorded = sorted(present - recorded)
    assert not unrecorded, (
        f"these shell test files carry no recorded case floor: {unrecorded}. Run "
        "`node --test --test-reporter=spec` over them, add their counts to "
        "SHELL_CASE_FLOORS with the commit they were measured at, and re-run. "
        "A witness with no floor is a witness whose deletion nothing notices."
    )


# --------------------------------------------------------------------------
# The mechanism, watched. Each check below feeds the reader a tree it is not
# reading, so that "the coverage check exists" is not the same claim as "the
# coverage check can fail".
# --------------------------------------------------------------------------


def test_the_coverage_check_reports_a_file_the_command_does_not_run() -> None:
    """A command that names three of the eight files runs three, and says so.

    Without this, the coverage check above could be narrowed — to a substring
    test, or to a command that names one file — and stay green while a shell
    witness went unrun. That is the exact neutering the project has been bitten
    by before, so it is tested against a synthetic command rather than argued.
    """
    files = [f"test/{name}" for name in sorted(SHELL_CASE_FLOORS)]
    named = {"config.test.mjs", "live-guard.test.mjs", "native-surface.test.mjs"}
    partial = "node --test " + " ".join(f"'test/{name}'" for name in sorted(named))
    missing = _missing_from_commands([partial], files)
    assert missing == sorted(f"test/{name}" for name in SHELL_CASE_FLOORS if name not in named), (
        f"a three-of-{len(files)} command must report the other "
        f"{len(files) - 3} as not run, not {missing}"
    )

    assert _missing_from_commands(["node --test 'test/*.test.mjs'"], files) == [], (
        "a glob over the test directory must cover every file — otherwise the CI "
        "command's own shape would be the thing that loses a witness"
    )

    nested = [*files, "test/nested/x.test.mjs"]
    assert _missing_from_commands(["node --test 'test/*.test.mjs'"], nested) == [
        "test/nested/x.test.mjs"
    ], (
        "Node's `test/*.test.mjs` does not cross a directory; a coverage check "
        "whose glob crossed one would report a nested witness as run when the CI "
        "command never reaches it"
    )

    split = [
        "node --test 'test/config.test.mjs' 'test/live-guard.test.mjs'",
        "node --test 'test/*.test.mjs'",
    ]
    assert _missing_from_commands(split, files) == [], (
        "two steps that together cover the directory are full coverage; reading "
        "the best single command instead would report the covered half as missing"
    )

    assert _missing_from_commands(["pnpm test"], files) == files, (
        "a command that names no file at all must be reported as running none"
    )


def test_the_case_counter_counts_the_declaration_form_the_floors_measured() -> None:
    """The floors count `test(` at the start of a line.

    A counter that matched `test(` anywhere would count a call inside a helper
    or a `describe()` body, and the recorded floors would then describe a shape
    the tree does not have. This holds the counting rule to the form the
    measurement used.
    """
    assert _node_case_count("test('one', () => {})\ntest('two', () => {})\n") == 2
    assert _node_case_count("describe('group', () => {\n  test('indented', () => {})\n})\n") == 0
    assert _node_case_count("const tested = 1\n") == 0


def test_the_import_reader_notices_a_package_and_ignores_what_the_job_provides() -> None:
    """The reader behind the no-package claim, checked against text it should and
    should not flag.

    A reader that reported nothing would keep the job's "installs no pnpm package"
    assertion green forever while a witness quietly began importing a package. A
    reader that flagged `node:fs` or `../src/live-guard.mjs` would be a check that
    cries wolf, and a check that cries wolf gets a `# noqa`-style exception within
    a week. Both halves are held here.
    """
    clean = (
        "import assert from 'node:assert/strict'\n"
        "import { guard } from '../src/live-guard.mjs'\n"
        "import { lockfileKeys } from '../../.github/shell-lockfile-keys.mjs'\n"
    )
    flagged_clean = _bare_imports(clean)
    assert flagged_clean == [], f"the reader flagged imports the job can satisfy: {flagged_clean}"

    dirty = (
        "import { load } from 'js-yaml'\n"
        "import { app } from 'electron'\n"
        "const { parse } = await import('yaml')\n"
    )
    flagged = _bare_imports(dirty)
    assert flagged == ["electron", "js-yaml", "yaml"], (
        f"the reader returned {flagged} for three package imports — a static or a "
        "dynamic import missed is the half the claim then does not cover"
    )

    # A specifier that only *looks* relative to the shell (a bare `test/…`) is a
    # package lookup to Node, and must be flagged rather than waved through.
    assert _bare_imports("import x from 'test/config.test.mjs'\n") == ["test/config.test.mjs"]


def test_the_name_check_refuses_a_name_it_cannot_render() -> None:
    """A matrix expression the matrix does not declare is not a name to compare.

    GitHub would render such a name as an empty substitution. A witness that
    compared the template text instead would call `shell-test (${x})` distinct
    from everything and stay green; the shared reader raises instead.
    """
    document = {
        "jobs": {
            "shell-test": {
                "name": "shell-test (${{ matrix.platform }})",
                "strategy": {"matrix": {"os": ["ubuntu-latest"]}},
            }
        }
    }
    with pytest.raises(UnrenderableJobNameError) as caught:
        rendered_job_names(document, "shell.yml")
    assert "matrix.platform" in str(caught.value), (
        f"the refusal must name the axis it could not render, not {caught.value!r}"
    )


def test_the_literal_matrix_name_shape_the_release_job_had_is_a_collision() -> None:
    """The D1 defect, reproduced against the shared reader.

    `release.yml` named a two-leg job `release-dependency-licences (matrix.os)` —
    parentheses, and the literal text `matrix.os` inside them, with no `${{ }}`.
    As a template it looks distinct from every other name. Rendered per leg it
    is the same name twice. This check is the reason the reader renders: it
    fails against the old shape, so it cannot be quietly reverted to comparing
    templates.
    """
    literal = {
        "jobs": {
            "release-dependency-licences": {
                "name": "release-dependency-licences (matrix.os)",
                "strategy": {"matrix": {"os": ["ubuntu-latest", "windows-latest"]}},
            }
        }
    }
    rendered = rendered_job_names(literal, "release.yml")
    assert rendered[0] == rendered[1] == "release-dependency-licences (matrix.os)", (
        f"the literal name renders as {rendered}: two legs, one check name"
    )

    fixed = {
        "jobs": {
            "release-dependency-licences": {
                "name": "release-dependency-licences (${{ matrix.os }})",
                "strategy": {"matrix": {"os": ["ubuntu-latest", "windows-latest"]}},
            }
        }
    }
    names = rendered_job_names(fixed, "release.yml")
    assert names == [
        "release-dependency-licences (ubuntu-latest)",
        "release-dependency-licences (windows-latest)",
    ], f"the expression renders per leg as {names}"


def test_a_job_with_no_matrix_expands_its_matrix_expressions_away() -> None:
    """A name with no matrix is not a name kept as written.

    **The hole this closes.** Before 2026-11-11 the shared reader routed a name
    through the substitution only when the job *had* a matrix, and appended the
    template verbatim otherwise. So two jobs with no matrix, each naming
    `${{ matrix.os }}` in its name, rendered as two distinct strings here — and
    GitHub, which expands an undefined `matrix.<axis>` to the **empty string**,
    would report them as `one ()` and `two ()`. The witness would call them
    unique while branch protection saw one check, which is the exact failure
    the `release-dependency-licences (matrix.os)` collision survived.

    **What the assertion holds.** A matrix expression in a name with no matrix
    expands to nothing, the parentheses stay, and the collision that expansion
    produces is *caught*. A reader that only expanded when a matrix existed
    would report the two names as distinct and pass.
    """
    collision = {
        "jobs": {
            "one": {"name": "quality (${{ matrix.os }})"},
            "two": {"name": "quality (${{ matrix.os }})"},
        }
    }
    rendered = rendered_job_names(collision, "synthetic.yml")
    assert rendered == ["quality ()", "quality ()"], (
        f"a name with no matrix rendered as {rendered}; GitHub expands an "
        "undefined matrix expression to the empty string, and the witness has "
        "to compare what GitHub reports"
    )
    assert len(set(rendered)) == 1, (
        f"two jobs of that shape reported {rendered} — distinct here, one check "
        "on GitHub, and a uniqueness witness that cannot see the collision is a "
        "witness that has been turned off"
    )

    plain = {"jobs": {"lint": {"name": "lint"}}}
    assert rendered_job_names(plain, "synthetic.yml") == ["lint"], (
        "a name with no matrix expression must survive the expansion untouched"
    )


def test_no_workflow_in_the_tree_declares_include_or_exclude(repo_root: Path) -> None:
    """The reader's scope and the tree's shape are recorded together.

    **The property.** `workflow_job_names` models a matrix as the cartesian
    product of its axes and refuses `include` / `exclude`. That refusal is only
    honest while the tree actually has no such leg — otherwise a workflow CI
    runs would be reported as an error rather than read. So the two facts are
    asserted in one place: **the tree declares neither key today** (measured at
    the revision named in this file's own floor anchor, and here, on every
    parsed workflow), and the reader refuses one that does, witnessed below.
    """
    documents = load_workflows(repo_root / ".github" / "workflows")
    assert documents, ".github/workflows declares no workflows"
    declared = [
        f"{path.name}: {job_key}.strategy.matrix.{key}"
        for path, document in documents
        for job_key, job in (document.get("jobs") or {}).items()
        if isinstance(job, dict)
        for key in _matrix_keys(job) & {"include", "exclude"}
    ]
    assert not declared, (
        "these matrix legs exist in the tree, and `workflow_job_names` does not "
        "model them: " + ", ".join(declared) + ". Extend the reader to GitHub's "
        "rules for them, then move this witness — do not relax the reader."
    )


def _matrix_keys(job: dict[str, Any]) -> set[str]:
    """The keys a job's `strategy.matrix` declares, whatever their shape."""
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    return set(matrix) if isinstance(matrix, dict) else set()


def test_the_reader_refuses_a_matrix_it_does_not_model() -> None:
    """`include` is refused rather than half-expanded.

    **Why refusal and not expansion.** GitHub merges an `include` entry into
    the combinations the axes produce, and adds a leg when the entry names a
    value no axis holds. An implementation that got that wrong would report a
    *set of job names* CI never runs — and a collision carried by a missing leg
    would read as unique. A refusal cannot be mistaken for a measurement.

    **What the assertion holds.** Both keys refuse, and the reason names the
    key it refused. A reader that skipped them as it used to would report the
    `include` leg's name at all, so this fails against the old behaviour.
    """
    for key in ("include", "exclude"):
        document = {
            "jobs": {
                "shell-test": {
                    "name": "shell-test (${{ matrix.os }})",
                    "strategy": {
                        "matrix": {
                            "os": ["ubuntu-latest"],
                            key: [{"os": "macos-latest"}],
                        }
                    },
                }
            }
        }
        with pytest.raises(UnrenderableJobNameError) as caught:
            rendered_job_names(document, "synthetic.yml")
        assert f"matrix.{key}" in str(caught.value), (
            f"the refusal for {key} must name the key it refused, not {caught.value!r}"
        )
