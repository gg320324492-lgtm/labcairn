"""The model-call path, watched.

**What is under test.** LC-P2-01: one product operation that asks a
declared model and records what came back, under the repository's
existing consent, budget, capability and refusal machinery — with the
bridge at the caller, so ``providers/`` keeps its disjointness from the
permission layer.

**And a fresh checkout cannot spend money by accident.** The dependency
is declared, and the tree carries no model.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

#: The suppliers the capability probe has measured, by the strings that
#: would mark a written configuration: a model id, and the endpoint a
#: configuration would carry. **The list grows only when the owner
#: authorises a supplier** — a supplier that is not authorised has no
#: entry, and an authorised one arrives here by editing this tuple, which
#: is a review of the writing, not an accident of it. ``api.minimax.cn``
#: is deliberately absent: it is already the destination the consent
#: demonstration sends *against* — data in an example, not configuration.
WRITTEN_MODEL_MARKERS: tuple[str, ...] = (
    "MiniMax-M3.1-Flash",
    "dashscope.aliyuncs",
)


def _pyproject(repo_root: Path) -> dict[str, Any]:
    """The parsed ``pyproject.toml``."""
    return tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))


def test_httpx_is_a_declared_dependency(repo_root: Path) -> None:
    """The HTTP client the provider path runs on is a version this project chose.

    It arrived transitively through ``pydantic-ai`` and was declared by
    nobody; the provider path is built on it, so it belongs in the
    runtime dependencies, and the lockfile moves with the declaration.
    """
    pyproject = _pyproject(repo_root)
    declared = [
        line for line in pyproject["project"]["dependencies"] if re.match(r"^httpx[\s>=<~!]", line)
    ]
    assert declared, "httpx is not in the runtime dependencies"

    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    root = next(package for package in lock["package"] if package["name"] == "labcairn")
    assert any(dep["name"] == "httpx" for dep in root["dependencies"]), (
        "the lockfile's root package does not depend on httpx"
    )
    locked = next(package for package in lock["package"] if package["name"] == "httpx")
    major, minor = (int(part) for part in locked["version"].split(".")[:2])
    assert (major, minor) >= (0, 27), f"httpx {locked['version']} is outside the declared range"


def test_no_model_id_endpoint_or_price_is_written_into_the_tree(repo_root: Path) -> None:
    """A supplier's identity is the operator's configuration, never the tree's.

    The repository's own configuration is the fake default: no
    ``configs/`` directory exists, because a configuration file is an
    operator's act. And no source file, example or project metadata
    carries a model id or a supplier endpoint — the probe's measured
    answers live in the store and the work orders' measurement
    histories, which are records, not configuration.
    """
    configs = repo_root / "configs"
    assert not configs.exists(), (
        "configs/ exists; the repository ships no configuration, and an"
        " operator's providers.json lives in a workspace, not in the tree"
    )
    surfaces = [
        repo_root / "pyproject.toml",
        *(path for path in (repo_root / "src").rglob("*.py")),
        *(path for path in (repo_root / "examples").rglob("*.py")),
    ]
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for marker in WRITTEN_MODEL_MARKERS:
            assert marker not in text, f"{surface.name} carries {marker!r}"


pytestmark = pytest.mark.integration
