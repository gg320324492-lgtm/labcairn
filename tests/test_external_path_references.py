"""The external-path ledger, watched.

**The property.** Three things, and all three are about this tree:

* every path under ``E:/labcairn-local`` that a tracked file names is in
  the ledger, so a record that starts naming a new external path is a
  path the ledger has to answer for;
* a path the ledger says is gone is **never named bare** — the paragraph
  that names it carries the wording the ledger requires, so a reader is
  never left with a path that is not there and no word that says so;
* a path that was renamed is named together with the path that replaced
  it, so a reader is never left with the old name alone.

**Why it needs watching.** On 2026-11-18 a pack was renamed, and four
records in this repository still pointed at the old name — a store that
is not on disk, a rehearsal copy that was deleted, and a directory of
mutants that was cleaned up. A reader who follows such a pointer finds
nothing, and nothing in the tree says so. The four records were repaired
on that date, and the repair is what this file watches: a rule that is
stated and not watched is not held.

**What runs where, and why this file is honest about it.** The three
properties above need only the tree, so they run on a runner. The fourth
check — whether the packs are actually where the ledger says they are —
needs a machine that has the packs, so it is **skipped where the root is
not there**, and it says so in the skip reason rather than passing
quietly. The reading is
[`docs/ci/external-path-reading.md`](../docs/ci/external-path-reading.md);
the ledger is [`docs/ci/external-paths.json`](../docs/ci/external-paths.json);
the tool that reads both is `scripts/check_external_paths.py`.

**The guard of the guard.** The checks above are machinery, and machinery
that nothing watches can be neutered while the tree stays green. So one
test here breaks the ledger on purpose and insists the checks notice.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

#: The tool the witness reads. It lives under ``scripts/`` because it is
#: also the development machine's entry point, and the witness loads it
#: the way the tool runs it — the house pattern, the same one
#: ``test_ci_shard_coverage.py`` uses for ``scripts/outsider_path.py``.
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_external_paths.py"

#: Where the packs live. A runner does not have this root; a development
#: machine does.
_PACK_ROOT = Path("E:/labcairn-local")


def _tool() -> ModuleType:
    """The checker, loaded the way the command line loads it."""
    spec = importlib.util.spec_from_file_location("check_external_paths_for_witness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ledger_path(repo_root: Path) -> Path:
    """The ledger, next to the repository it describes."""
    return repo_root / "docs" / "ci" / "external-paths.json"


def _load(repo_root: Path) -> tuple[Any, dict[str, Any], list[str]]:
    """The tool, the ledger, and the tracked files."""
    tool = _tool()
    ledger = tool.load_ledger(_ledger_path(repo_root))
    files = tool.tracked_files(repo_root)
    return tool, ledger, files


def test_the_ledger_is_well_formed(repo_root: Path) -> None:
    """The ledger says what it is, in the vocabulary the tool reads.

    A ledger whose shape has drifted is a ledger whose entries are read
    as defaults rather than as judgements, and the defaults are not
    what anybody decided.
    """
    tool, ledger, _files = _load(repo_root)
    problems = tool.well_formed_problems(ledger)
    assert not problems, problems


def test_every_path_a_record_names_is_in_the_ledger(repo_root: Path) -> None:
    """No tracked file names an external path the ledger does not answer for.

    This is the rule that keeps the ledger a ledger rather than a
    snapshot taken on one day. A record that names a new pack, a new
    scratch root or a new file inside a pack has to be declared, or the
    ledger stops describing what the repository says.
    """
    tool, ledger, files = _load(repo_root)
    problems = tool.coverage_problems(ledger, repo_root, files)
    assert not problems, problems


def test_a_path_that_is_gone_is_never_named_bare(repo_root: Path) -> None:
    """A record that names a path that is not there has to say so.

    A rename is not a defect; a bare pointer to the old name is. The
    wording the record carries is the ledger's, so the check is on the
    record rather than on a keyword list: the paragraph that names a
    gone path has to carry the phrase the ledger names for that path.
    """
    tool, ledger, files = _load(repo_root)
    problems = tool.announcement_problems(ledger, repo_root, files)
    assert not problems, problems


def test_a_rename_names_where_the_path_went(repo_root: Path) -> None:
    """The record that names the old address names the new one too.

    Otherwise the reader is left with the old name alone, which is the
    situation the rename was supposed to end.
    """
    tool, ledger, files = _load(repo_root)
    problems = tool.rename_problems(ledger, repo_root, files)
    assert not problems, problems


def test_the_paths_are_where_the_ledger_says(repo_root: Path) -> None:
    """The half that needs the packs, and says so when it cannot run.

    Whether ``E:/labcairn-local/...`` is on disk is a question about a
    machine. A runner has no pack root, so the check is skipped there —
    **skipped, not passed**: a runner cannot be the witness for it, and
    saying otherwise would be a witness that never ran.
    """
    tool, ledger, _files = _load(repo_root)
    if not _PACK_ROOT.exists():
        pytest.skip(
            f"{_PACK_ROOT} is not on this machine; the packs half of the "
            "external-path check cannot run here (it runs on a development "
            "machine: python scripts/check_external_paths.py)"
        )
    problems = tool.existence_problems(ledger)
    assert not problems, problems


def test_the_checks_catch_a_broken_ledger(repo_root: Path) -> None:
    """The guard of the guard: the checks must fail when the ledger is wrong.

    Three mutations, one per rule, each applied to a copy of the real
    ledger so the tree is not touched:

    * an announcement removed — the bare-pointer rule must notice;
    * an entry removed — the coverage rule must notice;
    * an expectation flipped — the existence rule must notice.

    A check that cannot fail is not a check, and this one is what makes
    the other three worth running.
    """
    tool, ledger, files = _load(repo_root)
    entries = tool.ledger_entries(ledger)

    dead = [
        entry
        for entry in entries
        if entry.get("kind") == "material" and entry.get("expectation") != "present"
    ]
    assert dead, "the ledger holds no gone material path, so the rule cannot be broken"
    broken = copy.deepcopy(ledger)
    for entry in tool.ledger_entries(broken):
        if entry.get("path") == dead[0].get("path"):
            entry["announcements"] = []
    problems = tool.announcement_problems(broken, repo_root, files)
    assert problems, "a gone material path with no announcement was not caught"

    live = [entry for entry in entries if entry.get("expectation") == "present"]
    assert live, "the ledger holds no present path, so the rule cannot be broken"
    broken = copy.deepcopy(ledger)
    broken["paths"] = [
        entry for entry in broken["paths"] if entry.get("path") != live[0].get("path")
    ]
    problems = tool.coverage_problems(broken, repo_root, files)
    assert problems, "a path named by a record and missing from the ledger was not caught"

    if not _PACK_ROOT.exists():
        pytest.skip("the packs are not on this machine, so the existence rule cannot be broken")
    broken = copy.deepcopy(ledger)
    for entry in tool.ledger_entries(broken):
        if entry.get("path") == live[0].get("path"):
            entry["expectation"] = "absent"
    problems = tool.existence_problems(broken)
    assert problems, "an expectation that contradicts the disk was not caught"
