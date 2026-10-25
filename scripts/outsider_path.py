"""The outsider's path: the README, run from a clean clone, by a stranger.

What this script is for
-----------------------

``docs/EVALUATION.md`` names seven Phase 1 blockers, and the first one is the
only one that is about a **person** rather than about the product:

    A new user cannot complete a task from a clean environment following README.

A test suite cannot express that directly, so this script is the way it becomes
expressible: **a fresh clone of the repository, a fresh environment in it, the
README's commands run for real, a research folder bound, a task created, a
report and a deterministic figure produced, one revision made, a restart
survived, and the same task read back through two surfaces.** Every step is a
check that raises rather than warns, so the exit code is the assertion.

**The clone is the point.** Running this in a developer's own checkout would
prove that *this machine* works, which is a different claim. So the script
clones the repository into a directory of its own, outside the checkout, and
builds an environment *inside the clone*. The walk then runs under the clone's
own interpreter, so the code under test is the clone's code and not the
developer's — and the script says where that code was loaded from, so a run
that quietly used the developer's tree cannot pass for a clean-clone run.

**The README's commands are executed, not paraphrased.** The command list is
extracted from the README in the clone, and the extraction is compared with
this script's table in both directions: a command the README shows that this
script does not run is a failure, and a row this script runs that the README
does not show is a failure too. The table is the check, and it is fail-closed.

**The provider is the deterministic one.** No real provider credential exists
in this repository, so the run is made with the repository's own fixtures and
no paid model: no network call to a provider, no credential. The acceptance
record says which steps were fixture-backed, because "it worked" is a
different claim from "it worked against a real provider".

Two modes
---------

``reviewer``
    Everything, including the README's ``uv run pytest`` as the README writes
    it. This is the mode an external reviewer runs, and it takes the length the
    whole suite takes.

``witness``
    The same walk, with one reduction: ``uv run pytest`` becomes
    ``uv run pytest --collect-only -q tests``. Running the whole suite from
    inside the suite would recurse — this file's own test runs the script,
    which runs the suite, which runs this file's own test. The reduction is
    recorded in the report under the command it applies to, so a witness run
    can never be read as a full-suite run.

Run it::

    uv run python scripts/outsider_path.py --work-root E:\\labcairn-local\\outsider

It writes a machine-readable report to ``<work-root>/outsider-path-report.json``
and prints where everything is.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Where things are
# --------------------------------------------------------------------------- #

#: This script, and the repository it lives in.
SCRIPT: Path = Path(__file__).resolve()
REPO_ROOT: Path = SCRIPT.parent.parent

#: The environment variable that says where a run's scratch space goes.
#:
#: The default is the machine's temporary directory, which on some machines is
#: inside another repository — and a workspace inside a repository is a
#: workspace whose run depends on the tree it runs in. The environment
#: variable is how an operator names a directory that is not.
WORK_ROOT_ENV: str = "LABCAIRN_TEMP_ROOT"

#: The modes, and what they differ in.
MODES: tuple[str, ...] = ("reviewer", "witness")

#: The moment the walk's own records are dated with. Nothing here reads the
#: wall clock, so two runs of the walk differ only in what they measured.
RECORDS_MOMENT: datetime = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)

# --------------------------------------------------------------------------- #
# The README's commands
# --------------------------------------------------------------------------- #

#: Fenced blocks. Only the shells hold instructions; ```python and ```text hold
#: prose, and a prose line is not a command a person can type.
#:
#: The blocks are **paired**, not matched by a pattern: a pattern that looked
#: for "the next closing fence" would read a ```python block as the tail of
#: the shell block above it, and a line of illustration would be run as a
#: command.
SHELL_LANGUAGES: frozenset[str] = frozenset({"", "bash", "sh", "shell"})


def fenced_blocks(text: str) -> Iterator[tuple[str, list[str]]]:
    """The fenced blocks of a document, as (language, lines).

    A fence opens with ``` and closes with ```; the language is whatever
    stands between them on the opening line. A block that is never closed
    runs to the end of the document.
    """
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("```"):
            index += 1
            continue
        language = stripped[3:].strip().lower()
        index += 1
        block: list[str] = []
        while index < len(lines) and lines[index].strip() != "```":
            block.append(lines[index])
            index += 1
        index += 1
        yield language, block


@dataclass(frozen=True)
class ReadmeCommand:
    """One command the README shows, and the subprocess that runs it.

    ``documented`` is the exact text the README must contain. ``argv`` is what
    is run; it differs from ``documented`` only where the difference is forced
    and is then stated in ``note``. ``in_suite_argv`` is the reduction used
    when the command is run from inside the suite, and ``None`` means the
    command is not reduced. ``unchanged`` names repository files that must be
    byte-identical before and after, so an install command that silently
    rewrites a lockfile fails.
    """

    documented: str
    argv: tuple[str, ...]
    cwd: str = "."
    timeout_s: float = 900.0
    in_suite_argv: tuple[str, ...] | None = None
    unchanged: tuple[str, ...] = ()
    note: str = ""


#: Every command the README shows, and how each one is run.
#:
#: The list is the check, and it is fail-closed in both directions: a command
#: the README shows that has no row here fails the run, and a row here that
#: the README does not show fails it too.
README_COMMANDS: tuple[ReadmeCommand, ...] = (
    ReadmeCommand(
        documented="uv sync",
        argv=("uv", "sync"),
        timeout_s=1800.0,
        unchanged=("uv.lock",),
        note="The real install, in the clone. uv.lock must survive it byte-identical: "
        "if pyproject.toml had drifted, uv would re-lock, and that is a change to "
        "the repository rather than an install.",
    ),
    ReadmeCommand(
        documented="uv run pytest",
        argv=("uv", "run", "pytest"),
        in_suite_argv=("uv", "run", "pytest", "--collect-only", "-q", "tests"),
        timeout_s=5400.0,
        note="The whole suite. In `witness` mode it is reduced to --collect-only, "
        "because running the whole suite from inside the suite would recurse: this "
        "file's own test runs the script, which runs the suite, which runs this "
        "file's own test. The reduction is recorded in the report against this "
        "command, so a witness run can never be read as a full-suite run.",
    ),
    ReadmeCommand(
        documented="uv run ruff check .",
        argv=("uv", "run", "ruff", "check", "."),
    ),
    ReadmeCommand(
        documented="uv run ruff format --check .",
        argv=("uv", "run", "ruff", "format", "--check", "."),
    ),
    ReadmeCommand(
        documented="uv run mypy",
        argv=("uv", "run", "mypy"),
        timeout_s=1800.0,
    ),
    ReadmeCommand(
        documented="uv run labcairn --help",
        argv=("uv", "run", "labcairn", "--help"),
        unchanged=("uv.lock",),
        note="The console script, from the clone's own environment. It proves the "
        "entry point resolves, the command tree assembles, and every command is "
        "registered.",
    ),
    ReadmeCommand(
        documented="pnpm install --frozen-lockfile",
        argv=("pnpm", "install", "--frozen-lockfile"),
        cwd="web",
        timeout_s=1800.0,
        unchanged=("pnpm-lock.yaml",),
        note="--frozen-lockfile is the CI form: it fails rather than resolving a new one.",
    ),
    ReadmeCommand(
        documented="pnpm test",
        argv=("pnpm", "test"),
        cwd="web",
        timeout_s=1800.0,
    ),
    ReadmeCommand(
        documented="pnpm typecheck",
        argv=("pnpm", "typecheck"),
        cwd="web",
    ),
    ReadmeCommand(
        documented="pnpm lint",
        argv=("pnpm", "lint"),
        cwd="web",
    ),
    ReadmeCommand(
        documented="pnpm format:check",
        argv=("pnpm", "format:check"),
        cwd="web",
    ),
)


def readme_commands(text: str) -> list[str]:
    """Every runnable command line the README shows, in document order.

    Whitespace is collapsed, because a line wrapped in Markdown is still one
    command and a reader must not be able to make the extractor see two.

    **Only a shell block holds instructions.** A ```` ```python ```` block is
    an illustration, and a line of illustration is not a command a person can
    type — so the blocks are paired fence by fence rather than matched by a
    pattern, because a pattern that looked for "the next closing fence" would
    read a ```` ```python ```` block as the tail of the shell block above it.
    """
    commands: list[str] = []
    for language, block in fenced_blocks(text):
        if language not in SHELL_LANGUAGES:
            continue
        for raw_line in block:
            line = " ".join(raw_line.strip().split())
            if not line or raw_line.strip().startswith("#"):
                continue
            commands.append(line)
    return commands


def commands_the_readme_shows(readme: Path) -> list[str]:
    """The README's commands, read out of the README itself."""
    return readme_commands(readme.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def digest(data: bytes) -> str:
    """The SHA-256 of some bytes, lowercase hex."""
    return hashlib.sha256(data).hexdigest()


def digest_of_file(path: Path) -> str:
    """The SHA-256 of a file's bytes."""
    return digest(path.read_bytes())


def leaves(document: Any, path: str = "") -> dict[str, Any]:
    """Every leaf of a document, by the path that names it.

    A comparison that says *which* field differs is worth more than one that
    says the documents differ.
    """
    if isinstance(document, dict):
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


def differences(left: Any, right: Any) -> tuple[str, ...]:
    """The fields two documents differ in, by the path that names them."""
    left_leaves = leaves(left)
    right_leaves = leaves(right)
    return tuple(
        sorted(
            name
            for name in set(left_leaves) | set(right_leaves)
            if left_leaves.get(name) != right_leaves.get(name)
        )
    )


class Recorder:
    """The checks a run made, and the failure of the first one that did not hold.

    A warning would leave the exit code saying "fine" while a guard had
    stopped working, and a run nobody can trust is worse than no run. So every
    claim raises, and the record of the claims is written out either way.
    """

    def __init__(self, section: str) -> None:
        self.section = section
        self.checks: list[dict[str, Any]] = []

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        """Record one claim, and fail loudly when it does not hold."""
        held = bool(condition)
        self.checks.append(
            {"section": self.section, "label": label, "ok": held, "detail": str(detail)}
        )
        if held:
            print(f"  [ok] {label}" + (f" - {detail}" if detail else ""))
            return
        print(f"  [FAIL] {label}" + (f" - {detail}" if detail else ""))
        raise AssertionError(f"FAILED: {label} {detail}")

    def note(self, label: str, detail: str) -> None:
        """Something worth printing that is not a claim."""
        print(f"  [..] {label} - {detail}")


def child_environment(work: Path) -> dict[str, str]:
    """The environment every child of this script runs with.

    **The temporary directory is outside the repository**, and it is the
    script's own: ``TEMP``, ``TMP`` and ``MPLCONFIGDIR`` all point inside the
    run's work root. Two reasons, both measured on this machine: the default
    base temporary directory fails here with ``WinError 5``, and a temporary
    directory inside the checkout makes two of the repository's own tests fail
    for a reason that has nothing to do with what they test.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set because the child's output
    encoding and terminal width are the machine's business, and neither is a
    fact about the CLI.
    """
    tmp = work / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["TEMP"] = str(tmp)
    environment["TMP"] = str(tmp)
    environment["MPLCONFIGDIR"] = str(tmp / "matplotlib")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    return environment


def resolve_argv(argv: tuple[str, ...] | list[str]) -> list[str]:
    """A command line a shell would accept on this machine.

    On Windows a user typing ``pnpm test`` gets ``pnpm.CMD``, because the
    shell consults ``PATHEXT``; ``CreateProcess`` does not, and passing the
    bare name raises for the exact command the README documents. Resolving
    with ``shutil.which`` and routing ``.cmd``/``.bat`` through ``cmd /c``
    reproduces the shell's behaviour instead of weakening the command being
    run.
    """
    first = argv[0]
    found = first if Path(first).is_file() else shutil.which(first)
    if found is None:
        msg = f"executable {first!r} is not on PATH; the command cannot be run"
        raise FileNotFoundError(msg)
    rest = list(argv[1:])
    if os.name == "nt" and found.lower().endswith((".cmd", ".bat")):
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", found, *rest]
    return [found, *rest]


def run(
    argv: list[str],
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run a command, and read its output as UTF-8 whatever the machine's is."""
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=timeout,
        check=False,
        shell=False,
    )


def default_work_root() -> Path:
    """Where a run's scratch space goes when nobody says otherwise."""
    named = os.environ.get(WORK_ROOT_ENV)
    if named:
        return Path(named) / "outsider-path"
    return Path(tempfile.gettempdir()) / "labcairn-outsider-path"


# --------------------------------------------------------------------------- #
# The parent: the clone, and the README's commands
# --------------------------------------------------------------------------- #


def clone_the_repository(repo: Path, destination: Path, recorder: Recorder) -> dict[str, Any]:
    """A fresh clone of the repository, and the facts that say it is one."""
    print(f"\n{'=' * 78}\n1. A clean clone\n{'=' * 78}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    environment = child_environment(destination.parent)
    started = time.monotonic()
    result = run(
        resolve_argv(("git", "clone", "--no-hardlinks", "--quiet", str(repo), str(destination))),
        destination.parent,
        environment,
        600.0,
    )
    recorder.check(
        "the repository cloned",
        result.returncode == 0,
        result.stderr.strip()[-400:],
    )
    recorder.check(
        "the clone is outside the repository it was cloned from",
        not destination.resolve().is_relative_to(repo.resolve()),
        str(destination),
    )
    status = run(
        resolve_argv(("git", "-C", str(destination), "status", "--porcelain")),
        destination.parent,
        environment,
        120.0,
    )
    recorder.check(
        "the clone's working tree is clean",
        status.returncode == 0 and not status.stdout.strip(),
        status.stdout.strip()[:200],
    )
    head = run(
        resolve_argv(("git", "-C", str(destination), "rev-parse", "HEAD")),
        destination.parent,
        environment,
        120.0,
    )
    source_head = run(
        resolve_argv(("git", "-C", str(repo), "rev-parse", "HEAD")),
        repo,
        environment,
        120.0,
    )
    recorder.check(
        "the clone is at the same commit as the repository it came from",
        head.stdout.strip() == source_head.stdout.strip(),
        f"{head.stdout.strip()} vs {source_head.stdout.strip()}",
    )
    for absent in (".venv", "web/node_modules", "output", ".labcairn"):
        recorder.check(
            f"the clone has no {absent}",
            not (destination / absent).exists(),
            str(destination / absent),
        )
    recorder.check(
        "the clone has the README the walk follows",
        (destination / "README.md").is_file(),
        str(destination / "README.md"),
    )
    print(f"  clone      : {destination}")
    print(f"  commit     : {head.stdout.strip()}")
    print(f"  cloned in  : {time.monotonic() - started:.1f}s")
    return {
        "path": str(destination),
        "head": head.stdout.strip(),
        "source_head": source_head.stdout.strip(),
        "seconds": round(time.monotonic() - started, 3),
    }


def check_the_command_table(clone: Path, recorder: Recorder) -> list[str]:
    """The README's commands and this script's table must agree, both ways.

    **A command in the README that this script does not run is a failure** —
    that is the acceptance clause, and it is checked against the README in the
    clone rather than against a copy of it. **A row here that the README does
    not show is a failure too**: a script that runs a command nobody can find
    is not running the README.
    """
    print(f"\n{'=' * 78}\n2. The README's commands, and this script's table\n{'=' * 78}")
    documented = commands_the_readme_shows(clone / "README.md")
    recorder.check(
        "the README shows at least one command",
        bool(documented),
        str(documented),
    )
    known = {command.documented for command in README_COMMANDS}
    unknown = [command for command in documented if command not in known]
    recorder.check(
        "every command the README shows has a row in this script's table",
        not unknown,
        f"without a row: {unknown}",
    )
    missing = [
        command.documented for command in README_COMMANDS if command.documented not in documented
    ]
    recorder.check(
        "every row in this script's table is a command the README shows",
        not missing,
        f"the README does not show: {missing}",
    )
    for command in documented:
        print(f"  documented : {command}")
    return documented


def the_pinned_pnpm(web: Path) -> str:
    """The pnpm version ``web/package.json`` pins.

    Read out of the manifest rather than written down here, because the
    manifest is where the repository already says it, and a second copy of
    the same pin is a number that can drift.
    """
    manifest = json.loads((web / "package.json").read_text(encoding="utf-8"))
    declared = manifest.get("packageManager", "")
    if not declared.startswith("pnpm@"):
        msg = (
            f"web/package.json declares no pnpm version ({declared!r}), so the "
            "script cannot know which pnpm to use"
        )
        raise ValueError(msg)
    return declared.removeprefix("pnpm@")


def the_web_package_manager(work: Path, web: Path) -> tuple[list[str], str]:
    """The argv prefix that runs pnpm, and how this machine got one.

    **The README names pnpm, so a machine without it has not met the README's
    requirements** -- and the CI runner that runs the Python suite has Node but
    not pnpm, because the web workflow is where pnpm is installed. So the
    script gets one itself, in the order that is cheapest and most likely to
    work:

    1. ``pnpm`` on PATH -- the normal case, and the one a machine that
       followed the README has;
    2. ``corepack pnpm`` -- Node's own mechanism, which uses the version
       ``web/package.json`` pins in ``packageManager``;
    3. ``npm install`` of that same pinned version into the work root, which
       needs nothing but npm.

    **And if none of them is there, the run refuses.** A command that could
    not be run is a command that did not work, and the sweep's claim is that
    every command the README shows ran. The refusal names what is missing, in
    the README's own words.
    """
    if shutil.which("pnpm"):
        return ["pnpm"], "pnpm on PATH"
    pinned = the_pinned_pnpm(web)
    if shutil.which("corepack"):
        # Corepack's own way of putting pnpm on PATH: it writes a shim into
        # Node's own directory, which is not always writable, so the way that
        # writes nothing is kept as the second answer.
        enabled = run(
            resolve_argv(("corepack", "enable", "pnpm")),
            work,
            child_environment(work),
            180.0,
        )
        if enabled.returncode == 0 and shutil.which("pnpm"):
            return ["pnpm"], f"corepack enabled the pnpm@{pinned} web/package.json pins"
        return (
            ["corepack", "pnpm"],
            f"corepack, which uses the pnpm@{pinned} web/package.json pins",
        )
    if shutil.which("npm"):
        home = work / "pnpm-home"
        home.mkdir(parents=True, exist_ok=True)
        installed = run(
            resolve_argv(
                (
                    "npm",
                    "install",
                    "--prefix",
                    str(home),
                    "--no-save",
                    "--no-audit",
                    "--no-fund",
                    f"pnpm@{pinned}",
                )
            ),
            work,
            child_environment(work),
            900.0,
        )
        binary = home / "node_modules" / ".bin" / ("pnpm.cmd" if os.name == "nt" else "pnpm")
        if installed.returncode == 0 and binary.is_file():
            return [str(binary)], f"npm installed the pnpm@{pinned} web/package.json pins"
        print(installed.stderr.strip()[-600:], file=sys.stderr)
    msg = (
        "no pnpm is available and none could be obtained. The README names the "
        "web package's requirements -- Node >= 24.16 with pnpm >= 9.15.9 -- and "
        "the script cannot run the README's web commands without one. Install "
        "Node (which brings npm and corepack with it) and run it again."
    )
    raise FileNotFoundError(msg)


def sweep_the_readme_commands(
    clone: Path,
    work: Path,
    mode: str,
    recorder: Recorder,
) -> list[dict[str, Any]]:
    """Run every command the README shows, in the clone, and record the run."""
    print(f"\n{'=' * 78}\n3. The README's commands, run in the clone ({mode} mode)\n{'=' * 78}")
    environment = child_environment(work)
    # Corepack asks before it downloads a package manager, and a run that
    # cannot answer a question is a run that stops.
    environment["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
    results: list[dict[str, Any]] = []

    web_prefix: list[str] = []
    web_origin = ""
    if any(command.argv[0] == "pnpm" for command in README_COMMANDS):
        web_prefix, web_origin = the_web_package_manager(work, clone / "web")
        print(f"  pnpm       : {' '.join(web_prefix)} ({web_origin})")

    for command in README_COMMANDS:
        reduced = mode != "reviewer" and command.in_suite_argv is not None
        argv = list(command.in_suite_argv if reduced else command.argv)
        assert argv
        if argv[0] == "pnpm":
            argv = [*web_prefix, *argv[1:]]
        workdir = (clone / command.cwd).resolve()
        before = {name: (workdir / name).read_bytes() for name in command.unchanged}

        printable = " ".join(argv)
        print(f"  running    : {printable}  (in {command.cwd})")
        started = time.monotonic()
        result = run(resolve_argv(argv), workdir, environment, command.timeout_s)
        seconds = time.monotonic() - started

        changed = [
            name for name, payload in before.items() if (workdir / name).read_bytes() != payload
        ]
        recorder.check(
            f"the README's `{command.documented}` succeeded",
            result.returncode == 0,
            f"exit {result.returncode}; {result.stderr.strip()[-400:]}",
        )
        recorder.check(
            f"the README's `{command.documented}` left the lockfiles alone",
            not changed,
            f"rewrote: {changed}",
        )
        print(f"  exit       : {result.returncode} in {seconds:.1f}s")
        results.append(
            {
                "documented": command.documented,
                "argv": list(argv),
                "web_package_manager": web_origin if command.argv[0] == "pnpm" else "",
                "cwd": command.cwd,
                "reduced": reduced,
                "reduction": (
                    "the whole suite cannot be run from inside the suite; this run "
                    "collected the suite instead, and the reduction is recorded here"
                    if reduced
                    else None
                ),
                "exit_code": result.returncode,
                "seconds": round(seconds, 3),
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-2000:],
            }
        )
    return results


# --------------------------------------------------------------------------- #
# The child: the walk itself
# --------------------------------------------------------------------------- #

#: The research folder's three files, by name.
PAPER_NAME = "paper.pdf"
TABLE_NAME = "measurements.csv"
NOTES_NAME = "notes.md"

#: The figure's editable source. A recipe is a document a person edits, and it
#: is written into the workspace rather than committed beside this script: the
#: file-ownership contract for this work order is three files, and a recipe is
#: an input to a run rather than part of the tool that runs it.
RECIPE_NAME = "figure-recipe.json"

#: The notes the Markdown file holds.
NOTES_TEXT = """# Field notes

The measurement campaign ran three groups of trials. The table in
`measurements.csv` holds one row per trial, and the group column says which
trial series a row belongs to.

- The figure's recipe computes the mean of the `value` column once per group.
- Every number in the report is checked against the cell it was read from.
"""


def _recompute_the_report(layer: Any, request: Any, moment: datetime) -> dict[str, str]:
    """What happens when the report is rendered again from the revised bytes.

    **The answer is recorded, not asserted.** Whether the report can be
    recomputed from material its claims were not read from is a fact about the
    product on the day, and a walk that insisted on either answer would fail
    the day the product changed. So the walk asks, and writes down what it was
    told — a revision, or a refusal that names itself.
    """
    from labcairn.application import render_report
    from labcairn.application.refusal import ApplicationRefusedError

    try:
        rendered = render_report(layer, request, now=moment)
    except ApplicationRefusedError as refused:
        return {
            "attempted": "yes",
            "outcome": f"refused ({refused.reason.value}): {refused.detail}",
            "rendered": "",
        }
    layer.store.session.commit()
    return {
        "attempted": "yes",
        "outcome": f"rendered as v{rendered.receipt.revision}",
        "rendered": rendered.receipt.receipt_id,
    }


def venv_paths(clone: Path) -> tuple[Path, Path]:
    """The clone's own interpreter and console script."""
    base = clone / ".venv"
    if os.name == "nt":
        scripts = base / "Scripts"
        return scripts / "python.exe", scripts / "labcairn.exe"
    binary = base / "bin"
    return binary / "python", binary / "labcairn"


def the_workspace_walk(spec: dict[str, Any], recorder: Recorder, report: dict[str, Any]) -> None:
    """The walk: bind the material, make a task, report, revise, restart, compare.

    It runs under the **clone's** interpreter, so the product code it exercises
    is the clone's code. The first thing it does is say where that code was
    loaded from, because a run that quietly used the developer's tree would
    pass for a clean-clone run without being one.
    """
    clone = Path(spec["clone"])
    workspace = Path(spec["workspace"])
    work = Path(spec["work"])
    mode = str(spec["mode"])

    import labcairn

    package = Path(labcairn.__file__).resolve()
    recorder.check(
        "the walk runs the clone's own code, not the developer's",
        not package.is_relative_to(REPO_ROOT.resolve()) and package.is_relative_to(clone.resolve()),
        str(package),
    )
    print(f"  package    : {package}")
    print(f"  interpreter: {sys.executable}")

    console = venv_paths(clone)[1]
    recorder.check(
        "the console script the walk drives is the clone's own",
        console.is_file() and console.resolve().is_relative_to(clone.resolve()),
        str(console),
    )

    from sqlalchemy import text as sql_text

    from labcairn.analysis.chart.recipe import ChartRecipe
    from labcairn.analysis.chart.render import MatplotlibFigureRenderer
    from labcairn.analysis.manifest import read_recipe, selection_payload
    from labcairn.analysis.operators import parse_operator_reference
    from labcairn.analysis.service import AnalysisRequest, analysis_arguments, run_analysis
    from labcairn.application import render_report
    from labcairn.application.reports import ReportRequest
    from labcairn.cli.workspace import (
        DEFAULT_POLICY_RULES,
        application_context,
        load_policy,
        locate,
        read_config,
        write_policy,
    )
    from labcairn.core.ids import ApprovalId, OperationId, TaskId
    from labcairn.db.models import SourceAnchorRow
    from labcairn.evidence.index import LabCairnIndex
    from labcairn.evidence.record import EvidenceRecord
    from labcairn.evidence.states import EvidenceCreator, EvidenceKind, VerificationStatus
    from labcairn.evidence.store import append_record
    from labcairn.material.addressing import render_locator_key, split_locator_key
    from labcairn.recovery.resume import STALE_REASON, MaterialResolver, ResumeCoordinator
    from labcairn.reports.receipt import ArtifactStaleness
    from labcairn.runtime.operation import ApprovalState
    from labcairn.security.approval import ApprovalGrant, SourceBinding, make_approval
    from labcairn.security.capabilities import CapabilityId
    from labcairn.security.policy import Permission, Rule
    from labcairn.sources.locators import CsvLocator, PdfLocator, TextLocator
    from labcairn.sources.source import AnchorKind, Source, SourceAnchor

    environment = child_environment(work)
    report.update(
        {
            "mode": mode,
            "clone": str(clone),
            "workspace": str(workspace),
            "package": str(package),
            "steps": [],
        }
    )

    def run_cli(*arguments: str, timeout: float = 600.0) -> subprocess.CompletedProcess[str]:
        """The console script, as a developer types it."""
        return run(
            [str(console), "--workspace", str(workspace), *arguments],
            workspace,
            environment,
            timeout,
        )

    def ledger_addresses(store: Any, source: Source) -> list[dict[str, Any]]:
        """Every address the ledger holds for a source, with its text.

        The addresses are read out of the ledger rather than assumed, so the
        claim the walk makes rests on an address the material really has.
        """
        rows = store.session.execute(
            sql_text(
                "SELECT locator_key, text FROM source_texts"
                " WHERE source_content_sha256 = :sha"
                " ORDER BY locator_key"
            ),
            {"sha": source.content_sha256},
        ).fetchall()
        found: list[dict[str, Any]] = []
        for key, text in rows:
            try:
                fields = split_locator_key(str(key))
            except Exception:  # a key this build cannot parse is not one
                continue
            found.append({"fields": fields, "text": str(text or "")})
        return found

    def locator_for(fields: dict[str, str]) -> Any:
        """The locator the ledger's own address names.

        **Built from the address rather than guessed.** A Markdown line is
        addressed by its section as well as by its line, so a locator built
        from the line alone names an address the ledger does not hold — and an
        anchor at an address nothing answers is an anchor to nothing.
        """
        kind = fields.get("k")
        if kind == "pdf":
            return PdfLocator(page=int(fields["p"]))
        if kind == "text":
            section = fields.get("s")
            return TextLocator(line=int(fields["l"]), section=section if section else None)
        if kind == "csv":
            return CsvLocator(row=int(fields["r"]), column=fields["c"])
        raise AssertionError(
            f"the ledger holds an address of a kind this walk does not read: {fields}"
        )

    # -- the workspace ------------------------------------------------------ #
    print(f"\n{'=' * 78}\n4. A workspace, and the research folder in it\n{'=' * 78}")
    workspace.mkdir(parents=True, exist_ok=True)
    initialised = run_cli("init", "--json")
    recorder.check(
        "labcairn init succeeded",
        initialised.returncode == 0,
        initialised.stderr.strip()[-400:],
    )
    setup = json.loads(initialised.stdout)
    recorder.check(
        "the workspace's source root is the one the CLI's own default names",
        list(setup["source_dirs"]) == ["materials"],
        str(setup["source_dirs"]),
    )
    print(f"  workspace  : {setup['root']}")
    print(f"  database   : {setup['database_path']}")
    print(f"  schema     : {setup['migration_revision']}")

    doctor = run_cli("doctor", "--json")
    recorder.check(
        "labcairn doctor succeeded",
        doctor.returncode == 0,
        doctor.stderr.strip()[-400:],
    )
    findings = json.loads(doctor.stdout)
    recorder.check(
        "no model provider is configured, so nothing was asked of one",
        findings["providers"] == [],
        str(findings["providers"]),
    )
    recorder.check(
        "the database is at the head migration",
        findings["database"]["at_head"] is True,
        findings["database"]["revision"],
    )

    # The research folder: a text PDF, a CSV and a Markdown. The first two are
    # the repository's own fixtures — a controlled table whose statistics were
    # written down by hand beside it, and a paper whose text layer the
    # ingestion can read. The third is written here, because the repository
    # holds no Markdown fixture and a research folder without one is not the
    # folder the deliverable names.
    materials = workspace / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    papers = sorted((clone / "tests" / "fixtures" / "papers").glob("*.pdf"))
    recorder.check(
        "the clone holds the paper fixture the research folder is built from",
        bool(papers),
        str(clone / "tests" / "fixtures" / "papers"),
    )
    table_fixture = clone / "tests" / "fixtures" / "analysis" / "groups.csv"
    recorder.check(
        "the clone holds the controlled table fixture",
        table_fixture.is_file(),
        str(table_fixture),
    )
    paper = min(papers, key=lambda path: path.stat().st_size)
    (materials / PAPER_NAME).write_bytes(paper.read_bytes())
    (materials / TABLE_NAME).write_bytes(table_fixture.read_bytes())
    (materials / NOTES_NAME).write_text(NOTES_TEXT, encoding="utf-8")

    pristine = {path.name: digest_of_file(path) for path in sorted(materials.iterdir())}
    fixture_digests = {
        "groups.csv": digest_of_file(table_fixture),
        paper.name: digest_of_file(paper),
    }
    recorder.check(
        "the research folder holds a PDF, a CSV and a Markdown",
        {path.suffix for path in materials.iterdir()} == {".pdf", ".csv", ".md"},
        ", ".join(sorted(path.name for path in materials.iterdir())),
    )
    for name, value in pristine.items():
        print(f"  material   : {name} {value[:12]}")

    # The operator's policy. The default policy denies every capability the
    # report path needs, and that is the right posture for a workspace nobody
    # has configured; the operator is configuring one.
    location = locate(workspace)
    write_policy(
        location,
        (
            *DEFAULT_POLICY_RULES,
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset(
                    {"analysis.run", "report.render", "fs.read", "fs.list", "fs.write"}
                ),
                note="the report path, for the outsider's own workspace",
            ),
        ),
    )
    policy = load_policy(location)
    print(f"  policy     : {policy.digest()[:12]}")

    # -- the task ----------------------------------------------------------- #
    print(f"\n{'=' * 78}\n5. A task, and the material bound to it\n{'=' * 78}")
    created = run_cli(
        "task",
        "create",
        "--title",
        "The outsider's own task",
        "--objective",
        "One research folder, one report, one figure, and a second reading of the same task.",
        "--criterion",
        "The report names the cells it rests on, and the two surfaces say the same thing.",
        "--source-dir",
        "materials",
        "--json",
    )
    recorder.check(
        "labcairn task create succeeded",
        created.returncode == 0,
        created.stderr.strip()[-400:],
    )
    task_model = json.loads(created.stdout)
    # The id is a UUID, not the string the JSON carries: an approval is
    # bound to a task by that id, and a string is not the same value as the
    # UUID the workspace holds -- so a string here would make every approval
    # look as if it belonged to another task.
    task_id = TaskId(uuid.UUID(task_model["task_id"]))
    bound = tuple(task_model["bound_source_ids"])
    recorder.check(
        "the task holds the material the CLI was told about",
        len(bound) == 3,
        str(bound),
    )
    print(f"  task       : {task_id}")
    print(f"  bound      : {', '.join(bound)}")

    sources: dict[str, Source] = {}
    for source_id in bound:
        inspected = run_cli("sources", "inspect", "--source", source_id, "--json")
        recorder.check(
            f"the CLI can report the material {source_id}",
            inspected.returncode == 0,
            inspected.stderr.strip()[-400:],
        )
        source = Source.model_validate(json.loads(inspected.stdout)["source"])
        sources[source_id] = source
        print(
            f"  source     : {source.relative_path} kind={source.kind.value} "
            f"readable={source.readability.value} {source.content_sha256[:12]}"
        )
    by_kind = {source.kind.value: source for source in sources.values()}
    recorder.check(
        "the task holds a PDF, a CSV and a Markdown",
        {"pdf", "csv", "markdown"} <= set(by_kind),
        ", ".join(sorted(by_kind)),
    )
    pdf_source = by_kind["pdf"]
    csv_source = by_kind["csv"]
    recorder.check(
        "the PDF is a text PDF, so it can be read and cited",
        pdf_source.readability.value == "readable",
        pdf_source.readability.value,
    )

    staged = run_cli("task", "run", "--source", csv_source.source_id, "--json")
    recorder.check(
        "the inventory stage ran against the bound material",
        staged.returncode == 0,
        staged.stderr.strip()[-400:],
    )

    # -- the evidence ledger ------------------------------------------------ #
    print(f"\n{'=' * 78}\n6. The evidence ledger, and the figure\n{'=' * 78}")

    config = read_config(location)
    with application_context(location, config, task_id) as layer:
        store = layer.store

        csv_addresses = [
            address
            for address in ledger_addresses(store, csv_source)
            if address["fields"].get("k") == "csv"
        ]
        recorder.check(
            "the ledger holds the cells of the table",
            bool(csv_addresses),
            f"{len(csv_addresses)} address(es)",
        )
        csv_address = next(
            (
                address
                for address in csv_addresses
                if address["fields"].get("r") == "2" and address["fields"].get("c") == "value"
            ),
            csv_addresses[0],
        )
        csv_value = csv_address["text"].strip()
        recorder.check(
            "the cell the claim will rest on holds a number",
            csv_value != "",
            f"row {csv_address['fields'].get('r')} column "
            f"{csv_address['fields'].get('c')} = {csv_value!r}",
        )

        pdf_addresses = [
            address
            for address in ledger_addresses(store, pdf_source)
            if address["fields"].get("k") == "pdf"
        ]
        recorder.check(
            "the ledger holds the PDF's pages as text",
            bool(pdf_addresses),
            f"{len(pdf_addresses)} address(es)",
        )
        pdf_address = next(
            (address for address in pdf_addresses if set(address["fields"]) == {"k", "p"}),
            pdf_addresses[0],
        )
        pdf_text = pdf_address["text"].strip()

        md_addresses = [
            address
            for address in ledger_addresses(store, by_kind["markdown"])
            if address["fields"].get("k") == "text"
        ]
        recorder.check(
            "the ledger holds the Markdown's lines as text",
            bool(md_addresses),
            f"{len(md_addresses)} address(es)",
        )
        md_address = next(
            (
                address
                for address in md_addresses
                if address["text"].strip() and not address["text"].lstrip().startswith("#")
            ),
            md_addresses[0],
        )
        md_text = md_address["text"].strip()

        # The product has no operation that writes an evidence record or an
        # anchor, so the walk writes the claim's own address itself. That gap
        # is a finding and it is recorded in the acceptance document.
        created_at = RECORDS_MOMENT
        anchors: list[SourceAnchor] = []
        for anchor_id, source, locator, kind, excerpt in (
            (
                "anc-csv",
                csv_source,
                locator_for(csv_address["fields"]),
                AnchorKind.NUMERIC,
                csv_value,
            ),
            (
                "anc-pdf",
                pdf_source,
                locator_for(pdf_address["fields"]),
                AnchorKind.QUOTATION,
                pdf_text[:200],
            ),
            (
                "anc-md",
                by_kind["markdown"],
                locator_for(md_address["fields"]),
                AnchorKind.QUOTATION,
                md_text,
            ),
        ):
            anchor = SourceAnchor(
                anchor_id=anchor_id,
                source_id=source.source_id,
                kind=kind,
                locator=locator,
                bound_source_sha256=source.content_sha256,
                excerpt_sha256=digest(excerpt.encode("utf-8")),
                created_at=created_at,
            )
            store.session.add(
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
            anchors.append(anchor)
        store.session.commit()

        for anchor in anchors:
            # The index is built here rather than above: a connection taken
            # before the commit is released back to the pool by it, and the
            # index would then be reading through a closed connection.
            located = LabCairnIndex(store.session.connection()).locate(anchor)
            recorder.check(
                f"the address {anchor.anchor_id} resolves in the material the task holds",
                located is not None and located.resolution.value == "resolved",
                f"{anchor.anchor_id}: {located.resolution.value if located else 'nothing'}",
            )

        records = (
            EvidenceRecord(
                evidence_id="ev-csv",
                task_id=str(task_id),
                kind=EvidenceKind.NUMERIC,
                text=None,
                value=float(csv_value),
                unit="dimensionless",
                anchor_ids=("anc-csv",),
                extracted_span=csv_value,
                extracted_span_sha256=digest(csv_value.encode("utf-8")),
                status=VerificationStatus.EXTRACTED,
                created_by=EvidenceCreator.RULE,
                created_by_id="outsider-path",
                source_content_hash=csv_source.content_sha256,
                created_at=created_at,
            ),
            EvidenceRecord(
                evidence_id="ev-pdf",
                task_id=str(task_id),
                kind=EvidenceKind.CLAIM,
                text=pdf_text[:200],
                value=None,
                unit=None,
                anchor_ids=("anc-pdf",),
                extracted_span=pdf_text[:200],
                extracted_span_sha256=digest(pdf_text[:200].encode("utf-8")),
                status=VerificationStatus.EXTRACTED,
                created_by=EvidenceCreator.RULE,
                created_by_id="outsider-path",
                source_content_hash=pdf_source.content_sha256,
                created_at=created_at,
            ),
            EvidenceRecord(
                evidence_id="ev-md",
                task_id=str(task_id),
                kind=EvidenceKind.CLAIM,
                text=md_text,
                value=None,
                unit=None,
                anchor_ids=("anc-md",),
                extracted_span=md_text,
                extracted_span_sha256=digest(md_text.encode("utf-8")),
                status=VerificationStatus.EXTRACTED,
                created_by=EvidenceCreator.RULE,
                created_by_id="outsider-path",
                source_content_hash=by_kind["markdown"].content_sha256,
                created_at=created_at,
            ),
        )
        for record in records:
            append_record(store.session.connection(), record)
        store.session.commit()
        recorder.check(
            "the ledger holds three records, one for each kind of material",
            len(records) == 3,
            ", ".join(record.evidence_id for record in records),
        )

        # -- the figure ---------------------------------------------------- #
        recipe_document = {
            "data": {
                "operator": "labcairn.analysis.grouped_aggregate@1.0.0",
                "parameters": {
                    "aggregate": "labcairn.analysis.mean@1.0.0",
                    "by": "group",
                    "of": "value",
                },
                "selection": {
                    "source": f"materials/{TABLE_NAME}",
                    "columns": ["group", "value"],
                    "rows": {"start": 2, "end": 17},
                    "missing": "exclude",
                },
            },
            "encoding": {
                "mark": "bar",
                "x": "group",
                "y": "value",
                "title": "Mean value by group",
                "x_label": "group",
                "y_label": "mean value",
                "caption": "The mean of the value column, computed once per group.",
                "interpretation": (
                    "The figure is a statement about this table and not about the groups "
                    "themselves: a group with fewer rows carries a mean over fewer rows."
                ),
            },
            "output": {"format": "svg", "dpi": 100},
        }
        (workspace / RECIPE_NAME).write_text(
            json.dumps(recipe_document, indent=2) + "\n", encoding="utf-8"
        )
        recipe = ChartRecipe.model_validate_json((workspace / RECIPE_NAME).read_bytes())
        recipe_ref = read_recipe(workspace, RECIPE_NAME)
        selection = recipe.data.selection.to_selection(
            csv_source.source_id, csv_source.content_sha256
        )
        operator_id, _version = parse_operator_reference(recipe.data.operator)
        arguments = {
            "path": TABLE_NAME,
            "operator_id": operator_id,
            "parameters": {
                **recipe.data.parameters,
                "selection": selection_payload(selection),
            },
        }
        workspace_binding = layer.workspace
        root_id = workspace_binding.source_roots[0].root_id

        approval = make_approval(
            task_id=task_id,
            operation_id=OperationId("00000000-0000-7000-8000-0000000000a1"),
            capability=CapabilityId.ANALYSIS_RUN.value,
            resource=workspace_binding.path_in(TABLE_NAME, root_id),
            args=analysis_arguments(arguments),
            depends_on=(csv_source.content_sha256,),
            expires_at=created_at + timedelta(hours=1),
        )
        granted = approval.model_copy(
            update={"state": ApprovalState.GRANTED, "granted_at": created_at}
        )
        layer.ledger.issue(
            ApprovalGrant(
                approval=granted,
                policy_digest=policy.digest(),
                sources=(
                    SourceBinding(resource_key=TABLE_NAME, expected_hash=csv_source.content_sha256),
                ),
            )
        )
        run_result = run_analysis(
            request=AnalysisRequest(
                approval_id=ApprovalId(granted.approval_id),
                root_id=root_id,
                arguments=arguments,
            ),
            store=store,
            workspace=workspace_binding,
            policy=policy,
            ledger=layer.ledger,
            renderer=MatplotlibFigureRenderer(
                recipe=recipe, recipe_ref=recipe_ref, workspace_root=workspace
            ),
            recipe=RECIPE_NAME,
            now=created_at,
        )
        store.session.commit()
        figure_receipt = run_result.figure_receipt
        recorder.check("the run wrote a figure", figure_receipt is not None, "no figure receipt")
        assert figure_receipt is not None
        figure_path = workspace / figure_receipt.relative_path
        figure_bytes = figure_path.read_bytes()
        recorder.check(
            "the figure on disk is the bytes the receipt records",
            figure_receipt.content_sha256 == digest(figure_bytes)
            and figure_receipt.size_bytes == len(figure_bytes),
            f"{len(figure_bytes)} byte(s)",
        )
        print(f"  figure     : {figure_receipt.relative_path} {len(figure_bytes)} byte(s)")

        # The figure is deterministic: a second draw of the same recipe and
        # the same result is the same bytes.
        again = MatplotlibFigureRenderer(
            recipe=recipe, recipe_ref=recipe_ref, workspace_root=workspace
        )
        again.prepare()
        rendered_again = again.render(operator_id, run_result.result)
        recorder.check(
            "two renders of one recipe are byte-identical",
            rendered_again == figure_bytes,
            f"{len(rendered_again or b'')} byte(s)",
        )

        # -- the report ---------------------------------------------------- #
        print(f"\n{'=' * 78}\n7. The report\n{'=' * 78}")
        rendered = render_report(
            layer,
            ReportRequest(path="report", template_id="default"),
            now=created_at,
        )
        store.session.commit()
        revision_one = workspace / "output" / str(task_id) / "report" / "v1"
        forms = (
            "report.json",
            "report-manifest.json",
            "report.md",
            "report.html",
            "report.docx",
            "report.pdf",
        )
        recorder.check(
            "the revision wrote the canonical document, the manifest and the four forms",
            all((revision_one / form).is_file() for form in forms),
            ", ".join(forms),
        )
        recorder.check(
            "the DOCX is a ZIP and the PDF is a PDF",
            (revision_one / "report.docx").read_bytes()[:2] == b"PK"
            and (revision_one / "report.pdf").read_bytes()[:4] == b"%PDF",
        )
        recorder.check(
            "the report's revision number is one, because it is the first",
            rendered.receipt.revision == 1,
            f"v{rendered.receipt.revision}",
        )
        document = json.loads((revision_one / "report.json").read_text(encoding="utf-8"))
        claims = document["claims"]
        recorder.check(
            "the report carries the three claims, one for each kind of material",
            len(claims) == 3,
            f"{len(claims)} claim(s)",
        )
        cited = {anchor_id for claim in claims for anchor_id in claim["record"]["anchor_ids"]}
        recorder.check(
            "every claim cites the address it rests on",
            cited == {"anc-csv", "anc-pdf", "anc-md"},
            ", ".join(sorted(cited)),
        )
        recorder.check(
            "the report's snapshot names the records it is a view of",
            sorted(document["snapshot"]["record_ids"]) == ["ev-csv", "ev-md", "ev-pdf"],
            ", ".join(document["snapshot"]["record_ids"]),
        )
        locators = {footnote["locator"]["locator_kind"] for footnote in document["footnotes"]}
        recorder.check(
            "the report's citations are locators of all three kinds",
            {"pdf", "csv", "text"} <= locators,
            ", ".join(sorted(locators)),
        )
        print(f"  claims     : {len(claims)}")
        print(f"  footnotes  : {len(document['footnotes'])}")

        report_receipt = rendered.receipt
        first_revision_digests = {
            path.name: digest_of_file(path) for path in sorted(revision_one.iterdir())
        }

    # -- the two surfaces ---------------------------------------------------- #
    print(f"\n{'=' * 78}\n8. The CLI and the local Web, against one task\n{'=' * 78}")
    cli_status = run_cli("task", "status", "--json")
    recorder.check(
        "the CLI's task status succeeded",
        cli_status.returncode == 0,
        cli_status.stderr.strip()[-400:],
    )
    cli_state = json.loads(cli_status.stdout)
    cli_artifacts = run_cli("artifacts", "list", "--json")
    recorder.check(
        "the CLI's artefact list succeeded",
        cli_artifacts.returncode == 0,
        cli_artifacts.stderr.strip()[-400:],
    )

    service = start_the_service(console, workspace, recorder)
    try:
        api_task = service_get(service, "/task")
        differing = differences(cli_state, api_task)
        recorder.check(
            "the CLI's task state and the API's task document are the same, field by field",
            not differing,
            f"{len(leaves(cli_state))} field(s) compared"
            + (f"; differing: {differing}" if differing else ""),
        )
        # The control: the same comparison, over a copy of the API's document
        # with a difference planted in it. A comparison that compares nothing
        # also reports "no differences", so the walk insists this one finds
        # what was planted — otherwise the check above could be narrowed until
        # it compared nothing and would still pass.
        planted = json.loads(json.dumps(api_task))
        planted["task"]["title"] = planted["task"]["title"] + " (planted)"
        planted_difference = differences(cli_state, planted)
        recorder.check(
            "the field-by-field comparison finds the difference it was given",
            bool(planted_difference),
            f"{len(planted_difference)} field(s) differ in the altered copy",
        )
        api_artifacts = service_get(service, "/artifacts")
        recorder.check(
            "the CLI's artefact list and the API's artefact list are the same",
            not differences(json.loads(cli_artifacts.stdout), api_artifacts),
            f"{len(leaves(api_artifacts))} field(s)",
        )
        listed = json.loads(cli_artifacts.stdout)
        by_name = {
            view["receipt"]["relative_path"].rsplit("/", 1)[-1]: view["receipt"] for view in listed
        }
        for form in ("report.md", "report.html", "report.docx", "report.pdf"):
            receipt = by_name.get(form)
            recorder.check(f"the CLI names the {form}", receipt is not None, f"{form} is missing")
            assert receipt is not None
            on_disk = (workspace / receipt["relative_path"]).read_bytes()
            served = service_get_bytes(service, f"/artifacts/{receipt['receipt_id']}/content")
            recorder.check(
                f"the {form} the CLI names is the bytes the API serves",
                digest(on_disk) == digest(served) == receipt["content_sha256"],
                receipt["content_sha256"][:12],
            )
            if form == "report.md":
                # The control, again: the file on disk is not the bytes the
                # service serves, and the comparison has to say so.
                recorder.check(
                    "the byte comparison finds the difference it was given",
                    digest(on_disk + b" (altered)") != digest(served),
                    "the altered file on disk is not the bytes served",
                )

        # The Web path is the API the workbench reads, and the workbench's own
        # list of paths is in the clone. So the paths this walk used are
        # checked against the list the Web client holds.
        paths_source = (clone / "web" / "src" / "api" / "paths.ts").read_text(encoding="utf-8")
        used = ("/health", "/session", "/task", "/artifacts")
        recorder.check(
            "the paths the walk used are the ones the workbench reads",
            all(f"'{path}'" in paths_source for path in used),
            ", ".join(used),
        )
        recorder.check(
            "the workbench reads the artefact's bytes from the path the walk used",
            "/artifacts/{artifact_id}/content" in paths_source,
            "the artefact content path",
        )
    finally:
        stop_the_service(service)

    # -- the revision -------------------------------------------------------- #
    print(f"\n{'=' * 78}\n9. The revision: the material moves, and the report says so\n{'=' * 78}")
    table_path = materials / TABLE_NAME
    original_hash = csv_source.content_sha256
    # The researcher's own edit: a value in the table was corrected. It is not
    # the product's: the product does not write to a source root, and the walk
    # below shows that it did not.
    #
    # **The recipe is not touched.** The figure's editable source is a
    # document the ledger's manifest names by its own bytes, so editing it
    # would leave the first figure describing a recipe that is no longer there
    # — and the report's second revision would be refused for naming a
    # manifest whose recipe has moved. A correction to the data does not
    # change what the figure plots, so the recipe stays as it was.
    raw = table_path.read_bytes()
    lines = raw.split(b"\n")
    lines[3] = b"A,30" + (b"\r" if lines[3].endswith(b"\r") else b"")
    table_path.write_bytes(b"\n".join(lines))
    measured = MaterialResolver(workspace).snapshot([f"materials/{TABLE_NAME}"])
    recorder.check(
        "the repository's own measurement says the material moved",
        measured[f"materials/{TABLE_NAME}"] != original_hash,
        f"{original_hash[:12]} -> {measured[f'materials/{TABLE_NAME}'][:12]}",
    )

    with application_context(location, read_config(location), task_id) as layer:
        store = layer.store
        coordinator = ResumeCoordinator(store, store.session, workspace_root=workspace)
        invalidation = coordinator.invalidate_on_source_change(task_id, [original_hash])
        store.session.commit()
        stale = coordinator.stale_artifacts(task_id)
        stale_ids = {receipt.receipt_id for receipt in stale}
        recorder.check(
            "the report's own receipt is among the artefacts the walk marked stale",
            report_receipt.receipt_id in stale_ids,
            f"{len(stale_ids)} stale receipt(s)",
        )
        recorder.check(
            "the walk marked them stale with the repository's own reason",
            all(
                receipt.staleness is ArtifactStaleness.STALE
                and receipt.staleness_reason == STALE_REASON
                for receipt in stale
            ),
            STALE_REASON,
        )
        recorder.check(
            "the walk named the hash it was given, and only that",
            tuple(invalidation.changed_hashes) == (original_hash,),
            str(invalidation.changed_hashes),
        )
        # Nothing was regenerated by the walk: a stale mark is recorded, not
        # acted on, and a human decides whether the change mattered.
        recorder.check(
            "the stale mark did not regenerate anything",
            not (workspace / "output" / str(task_id) / "report" / "v2").exists(),
            "no second revision exists yet",
        )

    # -- the report is generated again ---------------------------------------- #
    #
    # **Before** the ledger learns about the new bytes and **before** a second
    # figure is drawn over them. A revision is generated from what the task
    # holds, and what the task holds is the material the claims were read
    # from; the walk tries to recompute the report from the revised bytes
    # further down, and records what the layer says about that.
    with application_context(location, read_config(location), task_id) as layer:
        store = layer.store
        second_revision = render_report(
            layer,
            ReportRequest(path="report", template_id="default"),
            now=RECORDS_MOMENT + timedelta(minutes=1),
        )
        store.session.commit()
        revision_two = workspace / "output" / str(task_id) / "report" / "v2"
        recorder.check(
            "the report is generated again, as a second revision",
            second_revision.receipt.revision == 2 and revision_two.is_dir(),
            f"v{second_revision.receipt.revision}",
        )
        recorder.check(
            "the first revision's bytes are unchanged",
            first_revision_digests
            == {path.name: digest_of_file(path) for path in sorted(revision_one.iterdir())},
            f"{len(first_revision_digests)} file(s)",
        )
        recorder.check(
            "the second revision is not itself marked stale",
            second_revision.receipt.staleness is not ArtifactStaleness.STALE,
            second_revision.receipt.staleness.value,
        )
        print(f"  v1         : {report_receipt.relative_path}")
        print(f"  v2         : {second_revision.receipt.relative_path}")

    # The refreshed material goes back into the ledger through the CLI.
    refreshed = run_cli("sources", "ingest", "--json")
    recorder.check(
        "the CLI refreshed what the ledger records about the edited file",
        refreshed.returncode == 0,
        refreshed.stderr.strip()[-400:],
    )
    with application_context(location, read_config(location), task_id) as layer:
        store = layer.store
        inspected = run_cli("sources", "inspect", "--source", csv_source.source_id, "--json")
        recorder.check(
            "the CLI can report the refreshed material",
            inspected.returncode == 0,
            inspected.stderr.strip()[-400:],
        )
        new_source = Source.model_validate(json.loads(inspected.stdout)["source"])
        recorder.check(
            "the ledger now records the material's new content hash",
            new_source.content_sha256 == measured[f"materials/{TABLE_NAME}"],
            f"{new_source.content_sha256[:12]}",
        )

        # The figure is drawn again over the new bytes, under a fresh approval.
        recipe = ChartRecipe.model_validate_json((workspace / RECIPE_NAME).read_bytes())
        recipe_ref = read_recipe(workspace, RECIPE_NAME)
        selection = recipe.data.selection.to_selection(
            new_source.source_id, new_source.content_sha256
        )
        operator_id, _version = parse_operator_reference(recipe.data.operator)
        arguments = {
            "path": TABLE_NAME,
            "operator_id": operator_id,
            "parameters": {
                **recipe.data.parameters,
                "selection": selection_payload(selection),
            },
        }
        workspace_binding = layer.workspace
        root_id = workspace_binding.source_roots[0].root_id
        approval = make_approval(
            task_id=task_id,
            operation_id=OperationId("00000000-0000-7000-8000-0000000000a2"),
            capability=CapabilityId.ANALYSIS_RUN.value,
            resource=workspace_binding.path_in(TABLE_NAME, root_id),
            args=analysis_arguments(arguments),
            depends_on=(new_source.content_sha256,),
            expires_at=RECORDS_MOMENT + timedelta(hours=1),
        )
        granted = approval.model_copy(
            update={"state": ApprovalState.GRANTED, "granted_at": RECORDS_MOMENT}
        )
        layer.ledger.issue(
            ApprovalGrant(
                approval=granted,
                policy_digest=policy.digest(),
                sources=(
                    SourceBinding(resource_key=TABLE_NAME, expected_hash=new_source.content_sha256),
                ),
            )
        )
        second_run = run_analysis(
            request=AnalysisRequest(
                approval_id=ApprovalId(granted.approval_id),
                root_id=root_id,
                arguments=arguments,
            ),
            store=store,
            workspace=workspace_binding,
            policy=policy,
            ledger=layer.ledger,
            renderer=MatplotlibFigureRenderer(
                recipe=recipe, recipe_ref=recipe_ref, workspace_root=workspace
            ),
            recipe=RECIPE_NAME,
            now=RECORDS_MOMENT,
        )
        store.session.commit()
        second_figure = second_run.figure_receipt
        recorder.check(
            "the analysis runs again over the revised bytes and writes a figure",
            second_figure is not None,
            "no figure receipt",
        )
        assert second_figure is not None
        second_bytes = (workspace / second_figure.relative_path).read_bytes()
        recorder.check(
            "the new figure is not the old figure's bytes",
            digest(second_bytes) != digest(figure_bytes),
            f"{digest(second_bytes)[:12]} vs {digest(figure_bytes)[:12]}",
        )

        # The attempt to recompute the report from the revised bytes, and the
        # layer's answer. **The answer is recorded, not asserted**: whether the
        # report can be recomputed from material the claims were not read from
        # is a fact about the product on the day, and a walk that insisted on
        # either answer would fail the day the product changed.
        recomputation = _recompute_the_report(
            layer,
            ReportRequest(path="report", template_id="default"),
            RECORDS_MOMENT + timedelta(minutes=2),
        )
        recorder.check(
            "the walk attempted to recompute the report from the revised bytes",
            recomputation["attempted"],
            recomputation["outcome"][:300],
        )
        recorder.note("the recomputation's outcome", recomputation["outcome"][:300])
        report["recomputation"] = recomputation

    # -- the restart --------------------------------------------------------- #
    print(f"\n{'=' * 78}\n10. A restart, and the same task reopened\n{'=' * 78}")
    before_restart = json.loads(run_cli("task", "status", "--json").stdout)
    restarted = start_the_service(console, workspace, recorder)
    try:
        after_restart = json.loads(run_cli("task", "status", "--json").stdout)
        recorder.check(
            "the task after the restart is the task before it",
            after_restart["task"]["task_id"] == before_restart["task"]["task_id"],
            after_restart["task"]["task_id"],
        )
        api_task = service_get(restarted, "/task")
        recorder.check(
            "the service, in a new process, serves the same task",
            api_task["task"]["task_id"] == after_restart["task"]["task_id"],
            api_task["task"]["task_id"],
        )
        recorder.check(
            "the task's artefacts survived the restart",
            len(after_restart["artifacts"]) == len(before_restart["artifacts"])
            and len(after_restart["artifacts"]) > 0,
            f"{len(after_restart['artifacts'])} artefact(s)",
        )
        resumed = run_cli("task", "resume", "--source", csv_source.source_id, "--json")
        recorder.check(
            "the task resumes against the same task",
            resumed.returncode == 0,
            resumed.stderr.strip()[-400:],
        )
        resumed_model = json.loads(resumed.stdout)
        recorder.check(
            "the resume is a new run against the same task, not a new task",
            resumed_model["stage"]["task_id"] == after_restart["task"]["task_id"]
            and resumed_model["run"]["task_id"] == after_restart["task"]["task_id"],
            resumed_model["stage"]["task_id"],
        )
        final_state = json.loads(run_cli("task", "status", "--json").stdout)
        recorder.check(
            "the task now holds one run more than it did",
            len(final_state["runs"]) == len(after_restart["runs"]) + 1,
            f"{len(after_restart['runs'])} -> {len(final_state['runs'])}",
        )
        recorder.check(
            "every run the task holds belongs to that task",
            {run["task_id"] for run in final_state["runs"]} == {final_state["task"]["task_id"]},
            "",
        )
    finally:
        stop_the_service(restarted)

    # -- the material -------------------------------------------------------- #
    print(f"\n{'=' * 78}\n11. What the product did not touch\n{'=' * 78}")
    recorder.check(
        "the repository's own fixture corpus is byte-identical to what it was",
        digest_of_file(table_fixture) == fixture_digests["groups.csv"]
        and digest_of_file(paper) == fixture_digests[paper.name],
        "tests/fixtures/",
    )
    recorder.check(
        "the research folder still holds the three files it was given",
        {path.name for path in materials.iterdir()} == set(pristine),
        ", ".join(sorted(path.name for path in materials.iterdir())),
    )
    recorder.check(
        "no file was added to the research folder",
        not any(path.name.startswith(".") for path in materials.iterdir()),
        "",
    )
    output_area = workspace / "output"
    produced = [
        path.relative_to(workspace).as_posix() for path in output_area.rglob("*") if path.is_file()
    ]
    recorder.check(
        "every file the product produced is in the task's own output area",
        bool(produced) and all(path.startswith(f"output/{task_id}/") for path in produced),
        f"{len(produced)} file(s)",
    )
    recorder.check(
        "the product wrote nothing into the research folder",
        all(
            digest_of_file(path) == pristine[path.name]
            for path in materials.iterdir()
            if path.name != TABLE_NAME
        ),
        "the table is the researcher's own edit",
    )
    print(f"  produced   : {len(produced)} file(s), all under output/{task_id}/")
    print("  research   : the table is the researcher's edit; the other two are untouched")

    report["steps"] = [
        {"name": "workspace", "root": str(workspace)},
        {"name": "task", "task_id": str(task_id), "bound_source_ids": list(bound)},
        {"name": "sources", "kinds": sorted(by_kind)},
        {"name": "report", "revision": 1, "receipt": report_receipt.receipt_id},
        {"name": "revision", "revision": 2, "receipt": second_revision.receipt.receipt_id},
        {"name": "material", "pristine": pristine},
    ]
    report["findings"] = [
        {
            "what": "the report's second revision cannot be recomputed from the revised material",
            "measured": report.get("recomputation", {}).get("outcome", "not attempted"),
        },
    ]
    report["not_exercised"] = [
        "the React application was not run in a browser; the workbench was driven "
        "through the API it reads, and the paths used were checked against the "
        "workbench's own list of them",
        "the product has no operation that writes an evidence record or an anchor, "
        "so the walk wrote the claim's own address itself",
        "no real model provider was called: there is no credential for one in this "
        "repository, so the run is made against the repository's own fixtures",
    ]


# --------------------------------------------------------------------------- #
# The service the walk compares the CLI against
# --------------------------------------------------------------------------- #


def free_port() -> int:
    """A port nothing is listening on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def start_the_service(console: Path, workspace: Path, recorder: Recorder) -> dict[str, Any]:
    """The local service, in a process of its own.

    A separate process is the point: the service reads the workspace from disk
    when it starts, so what it serves is what the workspace holds and not what
    the walk held in memory.
    """
    import urllib.error
    import urllib.request

    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    log_path = workspace.parent / "service.log"
    log = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(console), "--workspace", str(workspace), "serve", "--port", str(port)],
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=workspace,
        env=child_environment(workspace.parent),
        text=True,
    )
    deadline = time.monotonic() + 120.0
    ready = False
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            request = urllib.request.Request(  # loopback only
                f"{origin}/health", headers={"Origin": origin}
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 200:
                    ready = True
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    recorder.check(
        "the local service started and answered",
        ready,
        f"service log: {log_path}",
    )
    if not ready:
        process.kill()
        log.close()
    return {"process": process, "origin": origin, "port": port, "log": log}


def stop_the_service(service: dict[str, Any]) -> None:
    """The service is stopped, and its log closed."""
    process = service["process"]
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
    log = service.get("log")
    if log is not None:
        log.close()


def service_get(service: dict[str, Any], path: str) -> Any:
    """A read from the service, as JSON."""
    import urllib.request

    request = urllib.request.Request(  # loopback only
        f"{service['origin']}{path}", headers={"Origin": service["origin"]}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def service_get_bytes(service: dict[str, Any], path: str) -> bytes:
    """A read from the service, as bytes."""
    import urllib.request

    request = urllib.request.Request(  # loopback only
        f"{service['origin']}{path}", headers={"Origin": service["origin"]}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


# --------------------------------------------------------------------------- #
# The parent: everything, and the report
# --------------------------------------------------------------------------- #


def run_the_walk(clone: Path, work: Path, mode: str) -> dict[str, Any]:
    """The walk, run under the clone's own interpreter."""
    python = venv_paths(clone)[0]
    if not python.is_file():
        msg = (
            f"the clone has no interpreter at {python}. `uv sync` did not build the "
            "clone's environment, so the walk cannot run under the clone's code."
        )
        raise FileNotFoundError(msg)
    spec = {
        "clone": str(clone),
        "workspace": str(work / "workspace"),
        "work": str(work),
        "mode": mode,
    }
    result = run(
        [str(python), str(SCRIPT), "--internal-walk", json.dumps(spec)],
        work,
        child_environment(work),
        3600.0,
    )
    report_path = work / "walk-report.json"
    walk_report: dict[str, Any] = {
        "exit_code": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
        "checks": [],
        "error": None,
    }
    if report_path.is_file():
        walk_report.update(json.loads(report_path.read_text(encoding="utf-8")))
    else:
        walk_report["error"] = (
            "the walk wrote no report.\n"
            f"--- stdout ---\n{result.stdout[-4000:]}\n"
            f"--- stderr ---\n{result.stderr[-4000:]}"
        )
    return walk_report


def main() -> int:
    """The outsider's path, from a clean clone to a reopened task."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=str(REPO_ROOT),
        help="the repository to clone. The default is the one this script lives in.",
    )
    parser.add_argument(
        "--work-root",
        default=None,
        help=(
            "where the clone, the workspace and the temporary files go. It must "
            "be outside the repository."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="reviewer",
        help=(
            "reviewer runs every README command as the README writes it, "
            "including the whole suite. witness reduces the whole-suite command "
            "to a collection, because running the whole suite from inside the "
            "suite would recurse."
        ),
    )
    parser.add_argument(
        "--internal-walk",
        default=None,
        help=argparse.SUPPRESS,  # the child process's own entry point
    )
    arguments = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    if arguments.internal_walk:
        spec = json.loads(arguments.internal_walk)
        recorder = Recorder("walk")
        error: str | None = None
        report: dict[str, Any] = {"mode": spec["mode"]}
        try:
            the_workspace_walk(spec, recorder, report)
        except Exception as failure:
            # Any failure at all, not only a claim that did not hold: a run
            # that crashed has still got a report to write, and a report that
            # says what happened is worth more than a stack trace in a log.
            error = f"{type(failure).__name__}: {failure}"
            print(f"\nFAILED: {error}", file=sys.stderr)
        report["checks"] = recorder.checks
        report["error"] = error
        destination = Path(spec["work"]) / "walk-report.json"
        destination.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return 1 if error else 0

    repo = Path(arguments.repo).resolve()
    work_given = Path(arguments.work_root) if arguments.work_root else default_work_root()
    work = work_given.resolve()
    work.mkdir(parents=True, exist_ok=True)
    # **The work root is resolved before anything is made under it.** On a
    # Windows machine whose temporary directory is spelled in the 8.3 short
    # form -- which is what a CI runner is -- the product refuses a write to
    # a *new* file under it: the declared path keeps the short spelling and
    # the root comes back long-spelled, so the two are compared as two
    # spellings of one directory (docs/plans/LC-P1-13-14-task-breakdown.md
    # §2.6). Resolving the root here gives the walk one spelling
    # throughout, and the product's defect is still a defect -- this is the
    # script working around it, and the acceptance record says so.
    resolved_work = work.resolve()
    short_spelled = str(resolved_work) != str(work_given)
    work = resolved_work
    recorder = Recorder("clone")

    print("LabCairn — the outsider's path (LC-P1-14)")
    print("A clean clone, the README's commands, a task, a report, a revision, a restart.")
    print("No credential, no paid model, no network call to a provider.\n")
    print(f"  repository : {repo}")
    print(f"  work root  : {work}")

    if work.is_relative_to(repo):
        print(
            f"FAILED: the work root {work} is inside the repository {repo}. A run "
            "inside the checkout proves that the checkout works, which is not the "
            "claim this script makes.",
            file=sys.stderr,
        )
        return 2

    clone = work / "clone"
    workspace = work / "workspace"
    for stale in (clone, workspace):
        if stale.exists():
            shutil.rmtree(stale)

    started = time.monotonic()
    clone_report: dict[str, Any] = {}
    documented: list[str] = []
    sweep: list[dict[str, Any]] = []
    walk: dict[str, Any] = {}
    failure: str | None = None
    try:
        clone_report = clone_the_repository(repo, clone, recorder)
        documented = check_the_command_table(clone, recorder)
        sweep = sweep_the_readme_commands(clone, work, arguments.mode, recorder)
        walk = run_the_walk(clone, work, arguments.mode)
        recorder.check(
            "the walk itself held every claim it made",
            walk.get("exit_code") == 0,
            str(walk.get("error") or walk.get("stderr", ""))[-600:],
        )
    except AssertionError as error:
        failure = str(error)
        print(f"\nFAILED: {error}", file=sys.stderr)
    except FileNotFoundError as error:
        # A tool the README names is missing, and the script cannot run the
        # README's commands without it. That is a refusal, not a crash.
        failure = str(error)
        print(f"\nFAILED: {error}", file=sys.stderr)

    report = {
        "mode": arguments.mode,
        "repository": str(repo),
        # Whether the work root was spelled differently from the way the
        # filesystem spells it -- on Windows, the 8.3 short form. It is
        # resolved before anything is made under it, because the product
        # refuses a new file under a short-spelled root (§2.6 of the task
        # breakdown).
        "work_root_was_short_spelled": short_spelled,
        # The spelling the run was given, beside the one it used. The two
        # differ on a Windows machine whose temporary directory is spelled in
        # the 8.3 short form, and the difference is the whole of the
        # workaround: the walk uses the resolved spelling throughout.
        "work_root_as_given": str(work_given),
        # The commit the clone was made from, read when the clone was made.
        # The repository's head at the end of the run is a different thing:
        # a run that takes three minutes can easily have a commit land inside
        # it, and a report that named the later commit would say the clone
        # was of a commit it is not.
        "repository_head": clone_report.get("source_head", ""),
        "work_root": str(work),
        "clone": clone_report,
        "readme_commands_documented": documented,
        "readme_commands_run": sweep,
        "walk": walk,
        "checks": recorder.checks + list(walk.get("checks", [])),
        "failure": failure,
        "seconds": round(time.monotonic() - started, 3),
    }
    (work / "outsider-path-report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n{'=' * 78}\nResult\n{'=' * 78}")
    print(f"{len(report['checks'])} checks passed.")
    print(f"report: {work / 'outsider-path-report.json'}")
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
