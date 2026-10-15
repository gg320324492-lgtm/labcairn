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
