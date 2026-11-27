r"""The tree carries no more Chinese *in total* than was measured, and the watch holds.

**The gap this closes.** ``scripts/cjk_ceilings.py`` measures, per tracked
file, the **longest** Han run, and ``tests/test_no_reference_leakage.py``
pins that number. A ceiling on the longest run is not a ban: it makes a new
*long* Chinese run an act someone registers deliberately. But it is blind to
the other direction. A name shorter than a file's existing longest run --
a four-character name appended to a file whose longest run is seven --
leaves the longest-run measurement **exactly where it was**, so the pin
stays green while the name sits in the tree. The pilot-records watch
(``tests/test_pilot_records_carry_no_names.py``) closes that for the pilot's
two globs, but a name anywhere else in the tree, or inside a file that already
carries a longer run, was outside both.

**The watch.** This pins the companion measurement: every Han character a
tracked file carries, from ``scripts/cjk_ceilings.py --totals``. It is a
*pin*, not a ban, in the same sense as its sibling -- it is re-measured and
re-pinned when the tree moves, and it reddens when a number moves for a
reason nobody signed. What it adds over the longest-run pin is the
direction the longest run cannot see: any addition, however short, moves a
file's whole Han load, so the number this pin holds.

**Why a pin and not a name list.** The corpus is Chinese; a Han character in
an English record is a transcription, and a denylist of known names would
find today's leak and not tomorrow's. The watch is on the *quantity* of
Chinese, measured and re-measured, so that the act of adding any of it is
never silent.

**The guard of a guard.** A tool that counts the tree's Chinese is a tool
that could stop seeing it. ``test_a_short_name_moves_the_totals_but_not_the_longest_run``
builds a scratch repository and appends a name shorter than the run already
there: it asserts the longest-run measurement did **not** move (the case the
old pin is blind to) and that the totals measurement **did** (the case this
pin catches). A broken ``--totals`` that merely re-reported the longest run
would leave the totals unchanged and redden here instead of blessing the
tree.

The synthetic characters this test builds are constructed at runtime from
code points, so the file spends none of the Han load it protects; none of
them is a person's name.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

#: The shipped measurement tool, driven the way this project's own tests
#: drive it -- as a subprocess of the console script, not an import.
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cjk_ceilings.py"

#: A synthetic anchor in the CJK unified-ideograph block. The characters this
#: file builds are counted by the tool's Han regex, but they are not a
#: person's name and carry no budget: they are constructed at runtime so the
#: file's own bytes spend none of the Han load the pin protects.
_SYNTHETIC_BASE = 0x4E00


def _han(n: int) -> str:
    """n synthetic Han characters, no two of them a name."""
    return "".join(chr(_SYNTHETIC_BASE + i) for i in range(n))


#: Every Han character each tracked file carried, measured 2026-11-27 by
#: ``scripts/cjk_ceilings.py --totals``. A complement to
#: ``CJK_RUN_CEILINGS`` in ``tests/test_no_reference_leakage.py``, which
#: pins the **longest** run: this one pins the **whole load**, so a short
#: addition that does not move the longest run still moves a number the pin
#: holds. It is a pin, not a ban -- re-measured and re-pinned when the tree
#: moves -- and it reddens in either direction: growth because a name or a
#: sentence was written in, shrinkage because a value was carried forward.
CJK_HAN_TOTALS: Final[dict[str, int]] = {
    "docs/plans/PHASE_4-execution-plan.md": 4193,
    "README.md": 3593,
    "README.zh-CN.md": 3432,
    "tests/test_readme_accuracy.py": 354,
    "docs/adr/ADR-0015-dataset-consent-and-access.md": 135,
    "docs/adr/ADR-0014-paper-revision-provenance.md": 121,
    "docs/adr/ADR-0016-model-proposal-and-human-confirmation.md": 98,
    "docs/plans/LC-P2-08-task-breakdown.md": 92,
    "src/labcairn/papers/alignment.py": 88,
    "docs/plans/PHASE_2-mentor-trajectory-work-orders.md": 85,
    "docs/acceptance/LC-P2-25-guard-of-the-guards.md": 79,
    "docs/research/upstream-study/openreview-py.md": 71,
    "docs/acceptance/LC-P2-07-fidelity-baseline.md": 50,
    "tests/test_version_alignment.py": 47,
    "docs/plans/PHASE_2-capability-reuse-matrix.md": 46,
    "src/labcairn/papers/versions.py": 43,
    "docs/research/upstream-study/PeerRead.md": 40,
    "docs/plans/P2-AMD-01-provider-and-data-options.md": 39,
    "docs/acceptance/LC-P3-08-trial-record-2026-11-22.md": 34,
    "src/labcairn/security/permissions.py": 34,
    "docs/acceptance/g5-review-records.md": 30,
    "docs/plans/LC-P2-14-ablation-protocol.md": 30,
    "docs/plans/PHASE_2-work-orders.md": 30,
    "src/labcairn/papers/duplicates.py": 26,
    "tests/docx_corpus.py": 25,
    "tests/test_version_contracts.py": 24,
    "docs/acceptance/LC-P3-08-review-2026-11-22-1.md": 23,
    "docs/adr/ADR-0017-feedback-chain.md": 20,
    "src/labcairn/skills/quality.py": 19,
    "docs/plans/LC-P2-06-task-breakdown.md": 17,
    "tests/test_consent_withdrawal.py": 17,
    "docs/acceptance/LC-P1-01-evidence.md": 15,
    "docs/research/upstream-study/XtraGPT.md": 15,
    "tests/test_paper_version_graph.py": 15,
    "tests/test_version_confirmation.py": 15,
    "docs/acceptance/P2-G0-evidence-pack.md": 14,
    "tests/test_version_duplicates.py": 13,
    "docs/acceptance/LC-P3-08-review-2026-11-22-readerB.md": 11,
    "tests/test_skill_quality.py": 11,
    "tests/test_status_consistency.py": 10,
    "docs/acceptance/LC-P3-08-exit-decision-2026-11-22.md": 9,
    "docs/acceptance/PR-1-independent-review.md": 9,
    "docs/plans/LC-P2-11-task-breakdown.md": 8,
    "docs/acceptance/LC-P3-05-clean-windows-drill-2026-11-20.md": 7,
    "docs/adr/ADR-0004-scientific-provenance-and-evidence-model.md": 7,
    "tests/test_material_regressions.py": 7,
    "scripts/cjk_ceilings.py": 6,
    "src/labcairn/db/models.py": 6,
    "tests/test_pilot_decisions.py": 6,
    "docs/acceptance/LC-P1-13-fixtures.md": 4,
    "tests/test_analysis_recipe.py": 4,
    "migrations/versions/0010_paper_version_graph.py": 3,
    "src/labcairn/roles/trajectory.py": 3,
    "tests/test_artifact_ledger_persistence.py": 2,
    "tests/test_cli_json_forms.py": 2,
    "tests/test_repo_root_guard.py": 2,
}


def _json_map(raw: str) -> dict[str, int]:
    """A JSON object of numbers, typed: ``json.loads`` is untyped on its own."""
    data: dict[str, int] = json.loads(raw)
    return data


def _measured_totals(repo_root: Path) -> dict[str, int]:
    """Ask the script for the totals. The measurement lives in one place."""
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--totals", "--root", str(repo_root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return _json_map(proc.stdout)


def _run_script(root: Path, flag: str) -> dict[str, int]:
    """Run the script against an arbitrary repository root, for the demonstration."""
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), flag, "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return _json_map(proc.stdout)


def _git(repo: Path, *args: str) -> None:
    """A git command in ``repo``, with an identity that is not the machine's."""
    finished = subprocess.run(
        [
            "git",
            "-c",
            "user.email=totals-pin@example.invalid",
            "-c",
            "user.name=The Totals Pin",
            "-C",
            str(repo),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert finished.returncode == 0, f"git {' '.join(args)} failed: {finished.stderr}"


def test_the_tree_carries_no_more_chinese_totals_than_was_measured(
    repo_root: Path,
) -> None:
    """The tree's whole Han load is pinned, in both directions.

    The repository is public and the pilot corpus is the owner's unpublished
    work. A name shorter than a file's longest run does not move the longest
    run, so the pin in ``test_no_reference_leakage.py`` is blind to it; this
    pin holds the file's *whole* Han load instead. Growth means a name or a
    sentence was written in that nobody signed. Shrinkage means a number was
    carried forward instead of re-measured -- the same failure the shard
    costs guard against, and the reason the assertion is an equality rather
    than a ``<=``.

    The table is checked against something real: the README must carry a
    large load, so a script that quietly returned an empty map would redden
    here instead of blessing the tree.
    """
    measured = _measured_totals(repo_root)
    assert measured.get("README.md", 0) >= 3000, (
        "the measurement no longer sees the bilingual README, so it cannot be "
        "trusting anything else either"
    )
    added = sorted(set(measured) - set(CJK_HAN_TOTALS))
    changed = sorted(
        p for p in measured if p in CJK_HAN_TOTALS and measured[p] != CJK_HAN_TOTALS[p]
    )
    removed = sorted(set(CJK_HAN_TOTALS) - set(measured))
    assert not added, f"files now carrying more Chinese than was measured: {added}"
    assert not changed, f"the Han total moved from what was pinned: {changed}"
    assert not removed, (
        f"a pinned file lost its Chinese and the table was not re-measured: {removed}"
    )


def test_a_short_name_moves_the_totals_but_not_the_longest_run(
    tmp_path: Path,
) -> None:
    """The guard of a guard: the tool that does the watching actually sees it.

    A file carries a seven-character Han run. A four-character name is
    appended, shorter than that run -- the shape a Chinese personal name has,
    and the shape the longest-run budget cannot see. The longest-run
    measurement must not move (asserting the *gap*), and the totals
    measurement must move (asserting the *fix*). The characters are
    synthetic, built at runtime, and no two of them spell a name.

    **What a broken implementation does here.** If ``--totals`` were merely
    re-reporting the longest run, the totals would stay at seven and the last
    assertion would fail. That is the failure that proves this is a witness
    for the property rather than a test that turns green for the wrong reason.
    """
    repo = tmp_path / "scratch"
    (repo / "docs").mkdir(parents=True)
    _git(repo, "init")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "scratch"\nversion = "0"\n', encoding="utf-8"
    )
    notes = repo / "docs" / "notes.md"
    notes.write_text("seed\n" + _han(7) + "\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "a seven-character run")

    longest_before = _run_script(repo, "--json")
    totals_before = _run_script(repo, "--totals")
    assert longest_before["docs/notes.md"] == 7
    assert totals_before["docs/notes.md"] == 7

    # Append a four-character name. It is shorter than the run already
    # there, so it is exactly the shape the longest-run budget cannot see.
    notes.write_text(notes.read_text(encoding="utf-8") + " " + _han(4), encoding="utf-8")
    _git(repo, "add", "docs/notes.md")
    _git(repo, "commit", "-m", "append a four-character name")

    longest_after = _run_script(repo, "--json")
    totals_after = _run_script(repo, "--totals")

    # The gap, stated as an assertion: the longest run did not move.
    assert longest_after["docs/notes.md"] == 7, (
        "the longest-run measurement must stay put when a shorter run is "
        "appended; this is the case the pin in test_no_reference_leakage.py "
        "is blind to"
    )
    # And the fix: the file's whole Han load moved by the name's length.
    assert totals_after["docs/notes.md"] == 11, (
        "the totals pin is the watch that reddens when a short name is "
        "appended to a file that already carries a longer run"
    )


@pytest.mark.parametrize("n", [1, 2, 4, 6])
def test_the_totals_pin_sees_a_name_of_any_length(tmp_path: Path, n: int) -> None:
    """Even a one- or two-character name moves a file's total.

    The pilot-records watch is a zero-tolerance Han check over two globs; a
    name anywhere else in the tree was outside it. The totals pin is over
    *every* tracked file, so a name of any length -- not just one shorter
    than a pre-existing run -- moves a number the pin holds.
    """
    repo = tmp_path / "scratch"
    (repo / "docs").mkdir(parents=True)
    _git(repo, "init")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "scratch"\nversion = "0"\n', encoding="utf-8"
    )
    notes = repo / "docs" / "notes.md"
    notes.write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "no Chinese yet")

    before = _run_script(repo, "--totals")
    assert "docs/notes.md" not in before, "a file with no Chinese has no entry"

    notes.write_text("seed\n" + _han(n) + "\n", encoding="utf-8")
    _git(repo, "add", "docs/notes.md")
    _git(repo, "commit", "-m", "a name of its own")

    after = _run_script(repo, "--totals")
    assert after["docs/notes.md"] == n, (
        f"a {n}-character name added a new entry and moved it to {n}; "
        "the totals pin sees a name of any length"
    )
