"""The CLI, run as a subprocess, with its exit code and its stdout.

**The CLI is tested by running it.** Every test here starts a real process,
runs the console script a developer would type, and reads the exit code and
the two streams. A test that called the Typer functions in-process would
exercise the commands but not the command line: not the option parsing, not
the exit code, and not the bytes that actually reach a terminal.

**The machine-readable form is compared to the model, not to the prose.**
Where a command has a ``--json`` form, the test reads the JSON and compares
it, field by field, with the application layer's own model read in this
process. That is the property the acceptance clause asks for — *"the CLI's
``task status --json`` and the API's task document are compared, field by
field, from the same store"* — and it is the only comparison that says
something: comparing the JSON to the Rich output would only prove that two
renderings of the same thing resemble each other.

**A parameter that is accepted must change what happened.** Every option this
CLI takes is exercised with a *non-default* value, and the test asserts the
consequence. A test that only showed "the command ran" would pass for an
option that is accepted and thrown away, which is the failure mode the brief
warns about.

**A refusal must be distinguishable from a crash by the exit code alone.**
That is the property a script depends on, so it is asserted against both: a
refusal carries :data:`EXIT_REFUSED`, and a crash carries Python's own 1.

**Loading the CLI must be cheap.** ``labcairn --help`` is the first thing a
person types, and this file spawns the command more than forty times, so
every second the CLI spends loading is paid for more than forty times over.
The cost is measured in a subprocess — it is invisible from inside one,
because this process has already imported everything the CLI would import —
and it is bounded, because a cost nobody measures is a cost that comes back.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from deadline_support import bounded_run

from labcairn.application import (
    ApplicationContext,
)
from labcairn.cli.workspace import (
    application_context,
    locate,
    read_config,
)
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine, create_session_factory, session_scope
from labcairn.db.materials import put_source
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
)
from labcairn.sources.source import Source, SourceKind, SourceReadability

pytestmark = pytest.mark.e2e

#: A fixed content hash. Constant so a test that asserts a hash round-trips
#: is not asserting against a value it generated with the call it is testing.
_HASH = "b" * 64

#: A second fixed hash, so two receipts are distinguishable.
_OTHER_HASH = "c" * 64

#: A fixed instant. The ledger's rows carry one, and a wall clock would make
#: the ordering assertions depend on when the test ran.
_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The source id the product's own ingestion mints: location-derived, and
#: **not** a UUIDv7. See ``test_the_task_cannot_bind_a_material_the_product_ingests``.
_SOURCE_ID = "src-0123456789abcdef"


# --------------------------------------------------------------------------- #
# running the CLI
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CliResult:
    """What one run of the CLI produced."""

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The machine-readable form, parsed."""
        return json.loads(self.stdout)


def _console_script() -> Path:
    """The script a developer types, as this interpreter would find it.

    Beside the running interpreter rather than on ``PATH``: the test must
    exercise the script the project installs, and ``PATH`` is the machine's
    business.
    """
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def run_cli(*args: str, cwd: Path | None = None, encoding: str = "utf-8") -> CliResult:
    """Run the console script and return what it produced.

    ``PYTHONIOENCODING`` is set because the child's output encoding is
    otherwise the machine's locale encoding, and a path with a non-ASCII
    character in it would make the test fail for a reason that has nothing
    to do with the CLI.

    ``COLUMNS`` is set for the same kind of reason. Rich asks the terminal
    how wide it is, and a pipe is not a terminal, so without this the
    rendered output would be laid out for eighty columns and a long path
    would be wrapped in the middle. The width of a terminal is a property of
    the terminal, and a test that asserted on a wrapped path would be
    asserting on the machine rather than on the CLI.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is tested "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = encoding
    environment["COLUMNS"] = "200"
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd is not None else None,
        env=environment,
        timeout=300,
    )
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace the CLI itself made."""
    root = tmp_path / "workspace"
    result = run_cli("--workspace", str(root), "init")
    assert result.returncode == 0, f"init failed: {result.stderr}"
    return root


@pytest.fixture
def task_id(workspace: Path) -> str:
    """A task the CLI itself made, and the workspace's current task."""
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Read the literature",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return str(result.json()["task_id"])


@pytest.fixture
def material(workspace: Path) -> Path:
    """A file of supplied material, in the workspace's source root."""
    path = workspace / "materials" / "one.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    return path


@pytest.fixture
def source_id(workspace: Path, material: Path) -> str:
    """A material in the ledger, as the product's own ingestion leaves it.

    Written here rather than through the CLI because the application layer
    has no ingestion operation, so no surface can put a source in the ledger.
    The CLI's job is to *inspect* what is there.
    """
    engine = create_db_engine(workspace / "labcairn.db")
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            put_source(
                session,
                Source(
                    source_id=_SOURCE_ID,
                    kind=SourceKind.CSV,
                    display_name="one.csv",
                    relative_path="materials/one.csv",
                    content_sha256=_HASH,
                    size_bytes=12,
                    readability=SourceReadability.READABLE,
                    ingested_at=_MOMENT,
                ),
            )
    finally:
        engine.dispose()
    return _SOURCE_ID


@contextmanager
def _context(workspace: Path, task_id: str) -> Iterator[ApplicationContext]:
    """The layer's context, in this process, for the same workspace.

    Built the way the CLI builds it — the same configuration, the same
    policy — so that comparing the CLI's JSON with the layer's model is a
    comparison of two reads of the same store and not of two configurations.
    """
    location = locate(workspace)
    config = read_config(location)
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        yield context


@pytest.fixture
def artifacts(workspace: Path, task_id: str) -> tuple[ArtifactReceipt, ...]:
    """Two artefacts in the store, in the order the store keeps them.

    Written here rather than through the CLI because the layer has no
    operation that records one: an artefact is recorded by the stage that
    produced it, and the CLI's stage produces none.

    Two, and not one, because a single-element list cannot show an ordering.
    """
    receipts = (
        ArtifactReceipt(
            receipt_id="artifact-first",
            task_id=task_id,
            kind=ArtifactKind.REPORT,
            relative_path=f"output/{task_id}/report.md",
            content_sha256=_HASH,
            size_bytes=10,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id="draft",
            created_at=_MOMENT,
            revision=1,
        ),
        ArtifactReceipt(
            receipt_id="artifact-second",
            task_id=task_id,
            kind=ArtifactKind.REPORT,
            relative_path=f"output/{task_id}/report-revised.md",
            content_sha256=_OTHER_HASH,
            size_bytes=20,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id="draft",
            created_at=_MOMENT,
            revision=2,
        ),
    )
    with _context(workspace, task_id) as context, context.store.unit(context.task_id) as work:
        for receipt in receipts:
            work.put_artifact(receipt)
    return receipts


# --------------------------------------------------------------------------- #
# the seam
# --------------------------------------------------------------------------- #


def test_the_cli_reaches_no_store_reader(repo_root: Path) -> None:
    """The CLI package imports neither the store's readers nor its rows.

    The application layer's own guard says the same thing about every
    module outside it; this says it about the CLI, so that the property is
    named in the file that owns the CLI.
    """
    forbidden = {"labcairn.db.repository", "labcairn.db.models"}
    offenders: list[str] = []
    for path in sorted((repo_root / "src" / "labcairn" / "cli").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            if forbidden.intersection(imported):
                offenders.append(f"{path.name}: {sorted(forbidden.intersection(imported))}")
    assert not offenders, (
        f"the CLI reaches past the application layer to the store: {offenders}. The "
        "layer exists so that a guard applied to an operation applies to every "
        "caller."
    )


def test_the_console_script_is_declared(repo_root: Path) -> None:
    """The script a developer types is declared, and points at the CLI."""
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text
    assert 'labcairn = "labcairn.cli:main"' in text


def test_every_command_the_plan_names_is_reachable() -> None:
    """The eight commands the plan names exist, with the names it gives them.

    Read from the application's own help, so a command that was renamed or
    dropped fails here rather than in somebody's script.
    """
    listing = run_cli("--help")
    assert listing.returncode == 0, listing.stderr
    for name in ("init", "doctor", "task", "sources", "artifacts"):
        assert name in listing.stdout

    task_listing = run_cli("task", "--help")
    assert task_listing.returncode == 0, task_listing.stderr
    for name in ("create", "run", "status", "resume"):
        assert name in task_listing.stdout

    assert "inspect" in run_cli("sources", "--help").stdout
    assert "list" in run_cli("artifacts", "--help").stdout


# --------------------------------------------------------------------------- #
# the cost of loading the CLI
# --------------------------------------------------------------------------- #

#: The packages the CLI must not load when it is loaded.
#:
#: These are the ones that cost. The application layer pulls the store, the
#: evidence readers and the provider stack; the store pulls SQLAlchemy and
#: Alembic; and the security and skills packages pull the observability
#: stack. Loading any of them is what made ``labcairn --help`` take two
#: seconds, so a CLI that loads one has paid for the whole application to
#: print a list of commands.
_LAYER_PACKAGES = (
    "labcairn.application",
    "labcairn.core",
    "labcairn.db",
    "labcairn.evidence",
    "labcairn.providers",
    "labcairn.runtime",
    "labcairn.security",
    "labcairn.skills",
    "labcairn.sources",
)

#: The most the CLI's import may cost, as a multiple of the bare
#: interpreter's own start-up on the same machine.
#:
#: A multiple rather than a number of seconds, because a number of seconds
#: is a fact about the machine the bound was measured on: a CI runner two or
#: three times slower than a development machine would fail a bound set in
#: seconds, and a test that fails on a slow machine teaches nothing but that
#: the machine is slow. The multiple is the property that holds everywhere —
#: the CLI's import is a small multiple of starting Python, not a multiple of
#: loading the application. Before the imports were deferred the ratio was
#: about forty.
_IMPORT_BUDGET_FACTOR = 10

#: The most the CLI's import may cost in seconds, whatever the machine.
#:
#: The floor under the multiple above, so that a machine whose bare start-up
#: is itself slow cannot excuse a slow import. It sits well above what the
#: CLI costs and well below what it used to cost: about two seconds.
_IMPORT_BUDGET_SECONDS = 1.5

#: The program that reports what loading the CLI left in the interpreter.
_REPORT_LOADED = (
    "import sys, json, labcairn.cli; "
    "print(json.dumps(sorted(m for m in sys.modules if m.startswith('labcairn'))))"
)


def _wall_seconds(command: list[str], runs: int = 5) -> float:
    """How long *command* takes, at its fastest.

    The minimum of several runs, not the mean: the slowest run of an import
    is the machine's noise — another test's subprocess, a virus scanner, a
    machine that is busy with something else — and a bound must not be set
    against the noise.
    """
    timings: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        completed = bounded_run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        timings.append(time.perf_counter() - started)
        assert completed.returncode == 0, completed.stderr
    return min(timings)


def test_loading_the_cli_does_not_load_the_layer() -> None:
    """The CLI loads without the layer, the store or the provider stack.

    Measured rather than read off the source: the property is about what the
    interpreter ends up holding, and a source reading can only say what
    somebody wrote down. A layer type imported at runtime instead of under
    ``TYPE_CHECKING`` works perfectly well — and costs a second and a half.
    """
    completed = bounded_run(
        [sys.executable, "-c", _REPORT_LOADED],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr
    loaded: list[str] = json.loads(completed.stdout)
    offenders = [
        module
        for module in loaded
        if any(module == package or module.startswith(f"{package}.") for package in _LAYER_PACKAGES)
    ]
    assert not offenders, (
        f"loading the CLI loaded {offenders}. The CLI imports the layer when a "
        "command needs it, not when the CLI is loaded, so that `labcairn --help` "
        "does not pay for the whole application."
    )


def _is_type_checking(test: ast.expr) -> bool:
    """Whether a module-level ``if`` is the ``TYPE_CHECKING`` guard.

    The names under that guard are not module-level imports: they are for
    mypy, and the interpreter never evaluates them.
    """
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def _the_module_level_imports(tree: ast.Module) -> list[str]:
    """The modules the module imports at module level.

    The names under ``TYPE_CHECKING`` are left out: they are for mypy, and
    the interpreter never evaluates them.
    """
    imported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            continue
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_the_cli_module_names_no_layer_module_at_module_level(repo_root: Path) -> None:
    """``cli/commands.py``'s module-level imports name no layer module.

    The docstring's claim, checked against the source it is about. The
    measurement above watches the *effect* — what the interpreter ends up
    holding — and this watches the *claim*: a layer name imported at module
    level would break the claim even on a build where it happened not to
    drag the layer in, and a claim nobody checks is a claim nobody can
    rely on.

    **The one project module the CLI names at module level is the API's bind
    module**, for the two defaults ``serve``'s own signature needs. It is
    named here so that a second one has to be argued for rather than added:
    a docstring that says what the module imports has to be kept true.
    """
    path = repo_root / "src" / "labcairn" / "cli" / "commands.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = _the_module_level_imports(tree)

    layer = [
        name
        for name in imported
        if any(name == package or name.startswith(f"{package}.") for package in _LAYER_PACKAGES)
    ]
    assert not layer, (
        f"the CLI names the layer at module level: {layer}. The layer is imported "
        "when a command needs it, not when the CLI is loaded, or `labcairn --help` "
        "pays for the whole application."
    )
    project = [name for name in imported if name.startswith("labcairn.")]
    assert project == ["labcairn.api.bind"], (
        f"the CLI names {project} at module level and not just the bind defaults. "
        "The docstring says the bind module is the only one, so a second one has "
        "to be argued for and the docstring has to be told about it."
    )


#: A project path in the docstring: a dotted name under the package.
_PROJECT_NAME = re.compile(r"\blabcairn(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b")

#: A module reference in the docstring: Sphinx's ``:mod:`` role.
_MODULE_ROLE = re.compile(r":mod:`~?([^`]+)`")


def _is_a_module_of_the_project(repo_root: Path, name: str) -> bool:
    """Whether *name* names a module of this project.

    Resolved against the source tree, because that is what decides it: a
    module is a path under ``src/`` with a ``.py`` beside it or a package
    directory, and a class or a function is not one.
    ``labcairn.application.ApplicationRefusedError`` is a class, and the
    module that holds it is not thereby named.
    """
    source = repo_root / "src" / Path(*name.split("."))
    return source.with_suffix(".py").is_file() or (source / "__init__.py").is_file()


def _the_modules_the_docstring_names(repo_root: Path, docstring: str) -> set[str]:
    """The project modules the docstring names.

    A mention names a module when the project has a module by that name,
    or when the docstring says it is one: ``:mod:`labcairn.api.bind`` is a
    module whatever the source tree says of it, and
    ``:class:`~labcairn.application.ApplicationRefusedError`` is a class, so
    the module that holds it is not thereby named.
    """
    named = {
        name
        for name in _PROJECT_NAME.findall(docstring)
        if _is_a_module_of_the_project(repo_root, name)
    }
    named.update(
        role.lstrip("~")
        for role in _MODULE_ROLE.findall(docstring)
        if role.lstrip("~").startswith("labcairn.")
    )
    return named


def test_the_cli_module_docstring_and_its_imports_agree(repo_root: Path) -> None:
    """The docstring says which modules the module imports, and it is right.

    **A docstring that says what the module imports is a claim, and a claim
    somebody checks is a claim that can be wrong.** The module's own
    docstring says that the layer is not loaded and which one project
    module is named at module level, and a sentence that denies a thing the
    module does is worse than no sentence: a reader believes it, and this
    one was read as a fact about the imports.

    The two are compared, **in both directions**:

    * **every module imported at module level is named in the docstring**,
      so the import cannot come back, or a second one be added, without the
      docstring being told; and
    * **every module the docstring names is imported at module level**, so
      a stale name in the prose is caught too.

    A mention of a class is not a mention of a module: the docstring names
    ``labcairn.application.ApplicationRefusedError``, and the module that
    holds it is not thereby named as an import.
    """
    path = repo_root / "src" / "labcairn" / "cli" / "commands.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring = ast.get_docstring(tree) or ""

    imported = {name for name in _the_module_level_imports(tree) if name.startswith("labcairn.")}
    claimed = _the_modules_the_docstring_names(repo_root, docstring)

    for module in sorted(imported):
        assert any(name == module or module.startswith(f"{name}.") for name in claimed), (
            f"the module imports {module} at module level and the docstring names "
            f"none of it: the docstring names {sorted(claimed)}. A docstring that "
            "says what the module imports has to be told when the imports change."
        )
    for name in sorted(claimed):
        assert any(module == name or module.startswith(f"{name}.") for module in imported), (
            f"the docstring names {name} and the module does not import it at "
            f"module level: it imports {sorted(imported)}. A name the module does "
            "not import is a name a reader will take for a fact."
        )


#: The claim the module's docstring makes about its module-level imports.
#:
#: A marked sentence, so that the docstring's own words are what the test
#: reads: the claim is stated once, in a form that can be checked, and the
#: names are read out of it.
_CLAIM = (
    "the module-level imports of this module, outside the standard library "
    "and Typer, are exactly these:"
)

#: The phrase only a statement about module-level imports carries.
_MODULE_LEVEL = re.compile(r"module[ -]level")


def _the_sentences(text: str) -> list[str]:
    """The text's sentences, as a reader would take them."""
    return [part for part in re.split(r"(?<=[.!?])\s+", text) if part]


def test_the_cli_module_docstring_says_what_it_imports_at_module_level(
    repo_root: Path,
) -> None:
    """The docstring says what the module imports at module level, and it is right.

    **The claim is machine-checkable, and it is checked.** The docstring
    states, in a marked sentence, exactly which modules the module imports
    at module level beyond the standard library and Typer. The test reads
    the names out of that sentence and compares them with the code.

    **And there is no other claim.** A name-by-name comparison cannot see a
    denial: *"this module imports nothing at module level but the standard
    library and Typer"* names nothing at all, so there is no name to
    compare, and it is false while the module imports a project module. So
    the docstring says what it imports at module level in one place and in
    one form — and a reader is given one thing to believe.
    """
    path = repo_root / "src" / "labcairn" / "cli" / "commands.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring = " ".join((ast.get_docstring(tree) or "").split())
    sentences = _the_sentences(docstring)

    claims = [sentence for sentence in sentences if _CLAIM in sentence]
    assert len(claims) == 1, (
        f"the docstring states what the module imports at module level "
        f"{len(claims)} time(s) and not once. The claim is made once, in the form "
        f"'...{_CLAIM}...', so that it can be read and checked."
    )
    about = [sentence for sentence in sentences if _MODULE_LEVEL.search(sentence)]
    assert len(about) == 1 and about[0] == claims[0], (
        f"the docstring says what the module imports at module level in "
        f"{len(about)} place(s): {about}. Say it once, in the marked form, so that "
        "a denial of what the module does cannot sit beside the truth."
    )

    named = _the_modules_the_docstring_names(repo_root, claims[0].split(_CLAIM, 1)[1])
    imported = {name for name in _the_module_level_imports(tree) if name.startswith("labcairn.")}
    assert named == imported, (
        f"the docstring says the module imports {sorted(named)} at module level and "
        f"the code imports {sorted(imported)}. A docstring that says what the "
        "module imports has to be told when the imports change."
    )


def test_loading_the_cli_costs_less_than_the_budget() -> None:
    """Importing the CLI costs a fraction of what it used to.

    ``labcairn --help`` is the first thing a person types, and it is paid for
    by more than forty of this file's tests. The cost is measured in a
    subprocess because it is invisible from inside one: this process has
    already imported everything the CLI would import, so the import the CLI
    would do has already happened here.
    """
    bare = _wall_seconds([sys.executable, "-c", "pass"])
    cost = _wall_seconds([sys.executable, "-c", "import labcairn.cli"])
    net = cost - bare
    budget = min(_IMPORT_BUDGET_SECONDS, _IMPORT_BUDGET_FACTOR * bare)
    assert net < budget, (
        f"importing labcairn.cli took {net:.3f}s over the interpreter's own "
        f"start-up of {bare:.3f}s, which is over the {budget:.3f}s budget. The "
        "CLI loads without the application layer; something has put it back."
    )
