"""The shell's version line is the workbench's version, and that is watched.

**What is under test.** The desktop shell's package manifest declares the
version electron-builder writes into the installer's own file name and its
product metadata. The workbench declares its version in ``pyproject.toml``.
On 2026-11-25 those two numbers were different: the shell read ``0.0.3`` --
the Phase 3 installer lineage's version, the one
``docs/plans/LC-P4-G0-baseline-freeze.md`` §3 records with its own digest --
while the workbench read ``0.1.0``. So the installer that carried v0.1.0's
product code called itself ``LabCairn Setup 0.0.3.exe``, and the release
record had to name the gap in its ``known_limits`` rather than let a reader
infer that the file name agreed with the bytes.

**Why a witness and not a note.** A version that can drift is a value that
has to be re-measured at every release, and the re-measurement is a person
remembering. The declarations below are read out of the tree and compared,
so the drift fails a test instead of shipping inside a file name.

**Which declarations, and why these.** The workbench's version is one number
written down in three places, and this file holds them to one another as
well as to the shell:

1. ``pyproject.toml``'s ``[project].version`` -- the distribution metadata,
   and the number an install carries;
2. ``src/labcairn/__init__.py``'s ``__version__`` -- what the installed
   package reports at runtime;
3. ``src/labcairn/api/app.py``'s ``API_VERSION`` -- what the running service
   reports in its OpenAPI document;

and the fourth is the one the gap was about:

4. ``shell/package.json``'s ``version`` -- what electron-builder puts in the
   installer's file name and product version.

**The packaging configuration is read too, because it has its own override.**
``shell/electron-builder.yml`` takes the version from the manifest, but it
also carries an ``extraMetadata`` block that is merged into the *packaged*
``package.json``. A ``version`` there would override the manifest's in the
installed application -- the same drift, one layer further in, and silent to
a reader of ``shell/package.json`` alone. So this file requires that block
to carry no version other than the manifest's.

**What this file deliberately does not do.** It does not assert that an
installer's bytes carry a particular digest: that is a build measurement,
and it lives in the release records (``docs/releases/v0.1.0.json`` and its
companion ``docs/releases/v0.1.0-artifact.json``), which name the artifact a
real build produced. This file reads the tree, so it holds before any build
exists; the records hold after one does.
"""

from __future__ import annotations

import ast
import json
import tomllib
from pathlib import Path
from typing import Any, Final

import yaml

#: Where the workbench declares its version, relative to the repository root.
PYPROJECT: Final = Path("pyproject.toml")

#: The package's own ``__version__``.
INIT: Final = Path("src") / "labcairn" / "__init__.py"

#: The service's ``API_VERSION`` -- what the running API reports.
API_APP: Final = Path("src") / "labcairn" / "api" / "app.py"

#: The shell's package manifest -- the version electron-builder reads.
SHELL_MANIFEST: Final = Path("shell") / "package.json"

#: The packaging configuration, and the block that can override the version.
BUILDER_CONFIG: Final = Path("shell") / "electron-builder.yml"


def _read_json(path: Path) -> Any:
    """The JSON document at *path*."""
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> Any:
    """The YAML document at *path*."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _assigned_string(path: Path, name: str) -> str:
    """The string value a module assigns to *name*.

    **Parsed, not pattern-matched.** A regular expression over the source
    would accept a commented-out assignment or a mention inside a docstring;
    this reads the module's syntax tree and takes the assignment the
    interpreter itself would take. The module is not imported: the file
    under test is the file in this checkout, and an import would read
    whichever copy the environment installed.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        msg = f"{name} in {path} is not assigned a plain string literal"
        raise AssertionError(msg)
    msg = f"{path} assigns no {name}"
    raise AssertionError(msg)


def _workbench_version(repo_root: Path) -> str:
    """The version the workbench declares in its packaging metadata."""
    document = tomllib.loads((repo_root / PYPROJECT).read_text(encoding="utf-8"))
    project = document.get("project")
    assert isinstance(project, dict), "pyproject.toml declares no [project] table"
    version = project.get("version")
    assert isinstance(version, str) and version, (
        f"pyproject.toml declares no project version, found {version!r}"
    )
    return version


def test_the_shell_manifest_carries_the_workbench_version(repo_root: Path) -> None:
    """The installer's file name is written from the workbench's version.

    **The property.** ``shell/package.json``'s ``version`` is the version
    electron-builder writes into ``LabCairn Setup <version>.exe`` and into
    the packaged application's product version, and it is the workbench's
    version -- the one ``pyproject.toml`` declares. An installer whose file
    name says ``0.0.3`` while its bytes carry ``0.1.0``'s product code is
    the gap this file exists to close.
    """
    workbench = _workbench_version(repo_root)
    manifest = _read_json(repo_root / SHELL_MANIFEST)
    shell = manifest.get("version")
    assert isinstance(shell, str) and shell, (
        f"shell/package.json declares no version, found {shell!r}"
    )
    assert shell == workbench, (
        f"shell/package.json declares version {shell!r} and the workbench "
        f"declares {workbench!r} (pyproject.toml). The installer's own file "
        f"name and product version are written from the manifest, so an "
        f"installer built from this tree would call itself "
        f"'LabCairn Setup {shell}.exe' while carrying the workbench's "
        f"{workbench}. Raise the shell's version to the workbench's, or lower "
        f"the workbench's -- in this tree, the workbench's version is the one "
        f"the release records name."
    )


def test_the_workbench_versions_agree_with_each_other(repo_root: Path) -> None:
    """The workbench's three version declarations are one number.

    **Why this matters here and not only in general.** The shell's manifest
    is aligned against the workbench's version, so the workbench's version
    has to *be* one number. ``pyproject.toml`` is the distribution metadata,
    ``src/labcairn/__init__.py`` is what the installed package reports at
    runtime, and ``API_VERSION`` is what the running service reports in its
    OpenAPI document. If those three disagreed, "the workbench's version"
    would be a choice rather than a fact, and the shell's manifest would be
    aligned against whichever one a reader happened to find first.
    """
    workbench = _workbench_version(repo_root)
    package = _assigned_string(repo_root / INIT, "__version__")
    api = _assigned_string(repo_root / API_APP, "API_VERSION")
    assert package == workbench, (
        f"src/labcairn/__init__.py declares __version__ = {package!r} and "
        f"pyproject.toml declares {workbench!r}"
    )
    assert api == workbench, (
        f"src/labcairn/api/app.py declares API_VERSION = {api!r} and "
        f"pyproject.toml declares {workbench!r}"
    )


def test_the_packaging_configuration_does_not_override_the_version(
    repo_root: Path,
) -> None:
    """No other file writes a version into the packaged application.

    **The property.** ``shell/electron-builder.yml`` takes the version from
    the manifest, but its ``extraMetadata`` block is merged into the
    *packaged* ``package.json``. A ``version`` there would override the
    manifest's in the installed application -- the same drift the manifest
    itself had, one layer further in, and invisible to a reader of
    ``shell/package.json`` alone. So the block must carry no version other
    than the manifest's.

    **And the block is parsed, not matched.** The shell's own configuration
    witness (``shell/test/packaging-config.test.mjs``) asserts the block's
    *text* -- that ``extraMetadata`` is followed by ``dependencies: null``.
    A third key under it leaves that text intact, so the text would still
    match while the override had arrived. This one reads the block as a
    mapping and looks at what is in it.

    **And the block itself must be a mapping.** ``extraMetadata`` may be
    absent (the block is optional), but if it is there it is a mapping of
    keys to values -- a scalar there would not be merged at all, and would
    silently take the override with it.
    """
    manifest = _read_json(repo_root / SHELL_MANIFEST)
    shell = manifest.get("version")
    assert isinstance(shell, str) and shell, (
        f"shell/package.json declares no version, found {shell!r}"
    )
    config = _read_yaml(repo_root / BUILDER_CONFIG)
    assert isinstance(config, dict), "electron-builder.yml is not a mapping"
    extra = config.get("extraMetadata")
    if extra is None:
        return
    assert isinstance(extra, dict), (
        f"electron-builder.yml's extraMetadata is {extra!r}, which is not a "
        f"mapping, so it cannot be merged into the packaged package.json"
    )
    assert "version" not in extra, (
        f"electron-builder.yml's extraMetadata carries version="
        f"{extra['version']!r}. That block is merged into the packaged "
        f"package.json, so the installed application would report "
        f"{extra['version']!r} while its installer is named for the "
        f"manifest's {shell!r}."
    )
