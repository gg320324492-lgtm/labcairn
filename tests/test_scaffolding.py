"""Scaffolding smoke tests — LC-P1-01 T02.

These prove the *scaffolding* works: the interpreter is the pinned one, the package
imports, and the packaging configuration says what it is supposed to say. They are
not product tests; there is no product code yet.

Deliberately at the repository root rather than under ``tests/``: ``tests/`` is
owned by a later task in LC-P1-01, and this file is the proof that the test
scaffolding itself is runnable. It should be folded into ``tests/`` once that
directory has an owner.

Note the division of labour with ``tests/test_no_reference_leakage.py`` (T05): that
file asserts the **built artifact** — real wheel and sdist member lists. Nothing
here inspects a build output, precisely so the two cannot disagree about what
"packaged" means.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import labcairn
import labcairn.core


def test_interpreter_is_the_pinned_312() -> None:
    """Guards docs/plans §4.1: the system Python is 3.10 and must never be used.

    A bare ``python -m pytest`` on this machine silently runs 3.10 and fails later,
    on PEP-695 syntax, somewhere confusing. This fails immediately and says so.
    """
    assert sys.version_info[:2] == (3, 12), f"expected Python 3.12, running {sys.version}"


def test_package_and_core_subpackage_import() -> None:
    """The LC-P1-01 amendment C-7 contract, checked in-tree.

    ``labcairn.core`` is the subpackage whose absence from the wheel was the
    reproduced setuptools failure. Importing it here proves the package tree is
    correct; T05 proves the wheel ships it.
    """
    assert labcairn.__version__ == "0.1.0"
    assert labcairn.core is not None
    assert labcairn.core.__name__ == "labcairn.core"


def test_core_resolves_inside_the_source_tree(repo_root: Path) -> None:
    """A stale copy installed elsewhere must not shadow the working tree.

    ``uv sync`` installs this project in editable mode, so ``labcairn.core.__file__``
    must sit under ``<repo_root>/src/``. If it does not, something installed a
    non-editable copy and every later test would be exercising the wrong files.
    """
    core_file = Path(labcairn.core.__file__).resolve()
    assert core_file.is_relative_to(repo_root / "src" / "labcairn"), (
        f"labcairn.core resolved to {core_file}, outside {repo_root / 'src' / 'labcairn'}"
    )


def test_build_backend_is_hatchling_with_a_recursive_package_root(repo_root: Path) -> None:
    """Config-level guard for LC-P1-01 amendment C-2.

    Reads ``pyproject.toml`` and asserts the two things that, if someone changes
    them, silently produce a wheel missing every subpackage:

    1. the backend is Hatchling, and
    2. ``[tool.hatch.build.targets.wheel] packages`` is exactly ``["src/labcairn"]``.

    A reader who takes this as a setuptools leaf-package list gets a wheel with no
    ``labcairn.core``, and the build still reports success. This is not the same
    check as T05's member-list assertion — this one fires at review time, before
    anyone builds.
    """
    pyproject: dict[str, Any] = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )

    build_system = pyproject["build-system"]
    assert build_system["build-backend"] == "hatchling.build", (
        f"build backend must stay Hatchling, found {build_system['build-backend']!r}"
    )
    assert build_system["requires"] == ["hatchling"], (
        f"build-system.requires must stay ['hatchling'], found {build_system['requires']!r}"
    )

    packages = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert packages == ["src/labcairn"], (
        f"wheel packages must stay the recursive root ['src/labcairn'], found {packages!r}"
    )

    # C-2: no MANIFEST.in. It is a setuptools mechanism; under Hatchling it would be
    # silently inert, and its presence would imply exclusions that are not happening.
    assert not (repo_root / "MANIFEST.in").exists(), (
        "MANIFEST.in must not exist under the Hatchling backend (amendment C-2)"
    )


# --------------------------------------------------------------------------- #
# the witness ledger
# --------------------------------------------------------------------------- #
#
# The tool `CLAUDE.md` asks for after every merge, and the reason it needs a
# witness of its own: it finds witnesses by matching the *shape* of a test's
# name in the source, and a shape that stopped matching would report
# "LOST -- none" over a tree that had lost one -- which is the green report,
# and the green report is the one nobody questions.

LEDGER = Path(__file__).resolve().parent.parent / "scripts" / "witness_ledger.py"

#: A test file with one top-level function and one method in a class, because
#: both shapes are what the tool has to see.
LEDGER_BEFORE = """
def test_a_witness_that_is_here() -> None:
    assert True


class TestAClass:
    def test_a_method_witness(self) -> None:
        assert True
"""

#: The same file with the top-level function gone -- a composition that kept
#: the file and lost the witness in it.
LEDGER_AFTER = """
class TestAClass:
    def test_a_method_witness(self) -> None:
        assert True
"""

#: The same file with one more witness in it and none taken away -- what an
#: ordinary change looks like, and what the tool must not report.
LEDGER_KEPT = """
def test_a_witness_that_is_here() -> None:
    assert True


class TestAClass:
    def test_a_method_witness(self) -> None:
        assert True


def test_a_new_witness() -> None:
    assert True
"""


def _git(repo: Path, *args: str) -> str:
    """A git command in ``repo``, with an identity that is not the machine's."""
    finished = subprocess.run(
        [
            "git",
            "-c",
            "user.email=ledger@example.invalid",
            "-c",
            "user.name=The Ledger",
            *args,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert finished.returncode == 0, f"git {' '.join(args)} failed: {finished.stderr}"
    return finished.stdout


def _ledger_repo(tmp_path: Path, second: str) -> tuple[Path, str, str]:
    """A repository with two revisions, the second holding ``second``."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    _git(repo, "init")
    (repo / "tests" / "test_a_file.py").write_text(LEDGER_BEFORE, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "the witnesses are here")
    before = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "tests" / "test_a_file.py").write_text(second, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "the second revision")
    return repo, before, _git(repo, "rev-parse", "HEAD").strip()


def _run_the_ledger(repo: Path, before: str, after: str) -> subprocess.CompletedProcess[str]:
    """The tool, run over two revisions of ``repo``."""
    return subprocess.run(
        [sys.executable, str(LEDGER), before, after, str(repo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_the_witness_ledger_names_a_witness_a_composition_lost(tmp_path: Path) -> None:
    """A tree that lost a witness is reported as one, by name."""
    repo, before, after = _ledger_repo(tmp_path, LEDGER_AFTER)

    finished = _run_the_ledger(repo, before, after)

    assert finished.returncode == 1, (
        "the ledger exited zero over a tree that lost a witness, which is the "
        "green report nobody questions:\n" + finished.stdout
    )
    assert "LOST" in finished.stdout, finished.stdout
    assert "test_a_witness_that_is_here" in finished.stdout, (
        "the ledger did not name the witness that was lost:\n" + finished.stdout
    )


def test_the_witness_ledger_leaves_a_method_witness_alone(tmp_path: Path) -> None:
    """A witness inside a class is a witness, and its loss is named too."""
    repo, before, after = _ledger_repo(tmp_path, "def test_something_else() -> None:\n    pass\n")

    finished = _run_the_ledger(repo, before, after)

    assert finished.returncode == 1, finished.stdout
    assert "test_a_method_witness" in finished.stdout, (
        "the ledger did not name the witness inside the class that was lost:\n" + finished.stdout
    )


def test_the_witness_ledger_reports_nothing_lost_when_nothing_was(tmp_path: Path) -> None:
    """A tree that kept every witness is reported as one, and exits zero."""
    repo, before, after = _ledger_repo(tmp_path, LEDGER_KEPT)

    finished = _run_the_ledger(repo, before, after)

    assert finished.returncode == 0, finished.stdout
    assert "LOST -- none" in finished.stdout, finished.stdout
    assert "test_a_new_witness" in finished.stdout, (
        "the ledger did not name the witness that was added, so the report is "
        "not telling the whole story:\n" + finished.stdout
    )
