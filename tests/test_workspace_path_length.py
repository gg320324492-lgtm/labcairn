"""Witness for the workspace write seam's path-length budget.

The atomic task-output write creates a sibling temporary file because
:func:`os.replace` is atomic only within a volume. That sibling name spends part
of the same visible path budget as the path above it. This file measures the
ceiling on the machine that runs it, writes through the real seam one character
past where the legacy 46-character name failed, and re-proves the negative
control in that same parent.

The repair shortens the task-output temporary name to the random tail of a
UUIDv7 id while keeping the ``".lc-write-"`` marker, so the older leftover sweep
in ``tests/test_workspace_boundaries.py`` remains meaningful. This file covers
the task-output seam. The sibling ``".lc-render-"`` seam in
``src/labcairn/analysis/chart/render.py`` is outside this file's sweep and is
not claimed as repaired here.
"""

from __future__ import annotations

import errno
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Final

import pytest

from labcairn.core.ids import TaskId, new_id
from labcairn.workspace import outputs as outputs_module
from labcairn.workspace.outputs import OutputRefusedError, TaskOutputArea
from labcairn.workspace.roots import Workspace, WorkspaceError

pytestmark = pytest.mark.integration

#: The marker the seam carried before the repair. Keeping it lets the existing
#: leftover sweep keep finding stray output temporary files.
LEGACY_TEMP_MARKER: Final[str] = ".lc-write-"

#: The legacy 46-character name, measured from its parts: the marker, a full 32
#: character UUID hex, and the suffix.
LEGACY_TEMP_NAME_CHARS: Final[int] = len(LEGACY_TEMP_MARKER + "0" * 32 + ".tmp")

#: NTFS refuses a single component longer than 255 characters, so the probe buys
#: depth with the directory above it instead of widening a component.
_MAX_PAD_CHARS: Final[int] = 250

#: The probe name and the layout premise use the same length. If one drifts from
#: the other, the negative control stops being a control.
_PROBE_NAME_CHARS: Final[int] = LEGACY_TEMP_NAME_CHARS

_NO_CEILING: Final[str] = (
    "Windows path semantics: no path-length ceiling is reachable inside a "
    "single 250-character component on this machine or in this layout, so there "
    "is no wall for the seam to clear (does not exist on this machine)"
)


def _visible(path: Path) -> int:
    """The visible characters of the spelling the seam hands to the OS."""
    return len(str(path))


def _is_path_length(exc: OSError) -> bool:
    """Whether *exc* is the path budget refusing, on either platform spelling.

    Windows answers ``ERROR_PATH_NOT_FOUND`` (errno 2) for a path whose parents
    exist but whose tail does not fit, and ``ERROR_FILENAME_EXCED_RANGE``
    (errno 206) for a component over the limit. POSIX answers ``ENAMETOOLONG``.
    The measured defect is exactly that asymmetry: the directory can be present
    while the exclusive open inside it reports "no such file or directory".
    """
    return exc.errno in {errno.ENOENT, errno.ENAMETOOLONG, errno.EINVAL, 206}


def _try_exclusive_create(directory: Path, name_chars: int) -> bool:
    """Whether an exclusive create of *name_chars* characters lands here."""
    name = "p" * name_chars
    created = directory / name
    try:
        created.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        if _is_path_length(exc):
            return False
        raise
    try:
        with created.open("xb"):
            pass
    except FileExistsError:
        # The name already existed. That is not the wall, and the search only
        # needs the truth about this length.
        return True
    except OSError as exc:
        if _is_path_length(exc):
            return False
        raise
    created.unlink(missing_ok=True)
    return True


def _measure_ceiling(probe_root: Path) -> int:
    """The largest visible path length at which an exclusive create succeeds."""
    probe_root.mkdir(parents=True, exist_ok=True)
    if _try_exclusive_create(probe_root / ("a" * _MAX_PAD_CHARS), _PROBE_NAME_CHARS):
        raise AssertionError(_NO_CEILING)

    low = 0
    high = _MAX_PAD_CHARS
    while low < high:
        middle = (low + high + 1) // 2
        if _try_exclusive_create(probe_root / ("a" * middle), _PROBE_NAME_CHARS):
            low = middle
        else:
            high = middle - 1
    if low == 0:
        raise AssertionError(_NO_CEILING)

    deepest = probe_root / ("a" * low)
    ceiling = _visible(deepest) + 1 + _PROBE_NAME_CHARS

    # Re-ask the step that settled the search: this length works and one more
    # character does not. If the probe cannot find a switch, it has measured
    # something other than the wall.
    assert _try_exclusive_create(deepest, _PROBE_NAME_CHARS), (
        f"the probe's own answer contradicts it: "
        f"{_visible(deepest) + 1 + _PROBE_NAME_CHARS} was reported as inside "
        "the budget and refused"
    )
    assert not _try_exclusive_create(probe_root / ("a" * (low + 1)), _PROBE_NAME_CHARS), (
        "no path-length switch was found inside the padding the probe can build"
    )
    return ceiling


@pytest.fixture(scope="module")
def ceiling(tmp_path_factory: pytest.TempPathFactory) -> int:
    """The exclusive-create ceiling, measured once for this run."""
    try:
        return _measure_ceiling(tmp_path_factory.mktemp("maxpath-probe"))
    except AssertionError as exc:
        if _NO_CEILING in str(exc):
            pytest.skip(_NO_CEILING)
        raise


def _near_ceiling_workspace(base: Path, ceiling: int) -> tuple[Workspace, str, Path]:
    """A real workspace and a parent tuned so a 46-character name lands past it."""
    selected_root = base / "ws"
    selected_root.mkdir(parents=True, exist_ok=True)
    workspace = Workspace.bind(selected_root, task_id=TaskId(new_id()))
    parent_prefix = workspace.output_root.path / "budget"

    fixed = _visible(parent_prefix) + 1
    pad = ceiling + 1 - LEGACY_TEMP_NAME_CHARS - 1 - fixed
    if not 1 <= pad <= _MAX_PAD_CHARS:
        pytest.fail(_NO_CEILING)

    key = f"budget/{'a' * pad}/result.bin"
    return workspace, key, parent_prefix / ("a" * pad) / "result.bin"


def _plain_workspace(base: Path) -> tuple[Workspace, str, Path]:
    """A real workspace and an ordinary key, with no padding."""
    selected_root = base / "ws"
    selected_root.mkdir(parents=True, exist_ok=True)
    workspace = Workspace.bind(selected_root, task_id=TaskId(new_id()))
    key = "budget/nested/result.bin"
    return workspace, key, workspace.output_root.path / key


def _seam_temp_name(hex_digits: str) -> str:
    """Rebuild the seam's temp name through the product's own naming function.

    The length of this name is the quantity under test. Calling the product's
    function rather than rebuilding the string here means a change inside
    ``_temporary_name`` is caught by the witnesses that plant or count names,
    instead of being hidden behind a duplicated constant.
    """
    builder: Callable[[str], str] | None = getattr(outputs_module, "_temporary_name", None)
    if builder is not None:
        return builder(hex_digits)
    marker = getattr(outputs_module, "_WRITE_TEMP_MARKER", LEGACY_TEMP_MARKER)
    suffix = getattr(outputs_module, "_WRITE_TEMP_SUFFIX", ".tmp")
    entropy = getattr(outputs_module, "_TEMP_NAME_CHARS", None)
    token = hex_digits[-entropy:] if isinstance(entropy, int) else hex_digits
    return f"{marker}{token}{suffix}"


def _output_files(workspace: Workspace) -> list[Path]:
    """Every file in the task's output area, deliberately unfiltered."""
    files = (path for path in workspace.output_root.path.rglob("*") if path.is_file())
    return sorted(files, key=str)


def _sweep_output_area(workspace: Workspace, destination: Path) -> Iterator[Path]:
    """Yield every output-area file that is not *destination*."""
    for path in workspace.output_root.path.rglob("*"):
        if path.is_file() and path != destination:
            yield path


def test_the_seam_writes_one_character_past_where_the_legacy_name_refused(
    tmp_path: Path, ceiling: int
) -> None:
    """The repair's own witness: the real seam, in a real layout, at the wall."""
    workspace, key, destination = _near_ceiling_workspace(tmp_path, ceiling)
    data = b"the write seam pays its own path budget"

    try:
        receipt = TaskOutputArea(workspace).write(key, data, fsync=False)
    except FileNotFoundError as exc:
        pytest.fail(
            f"the seam's temporary name still crosses the path budget at this "
            f"depth ({exc}); the negative control refuses a 46-character name "
            "in the same parent"
        )

    assert receipt.absolute_path == destination
    assert receipt.absolute_path.read_bytes() == data
    assert receipt.size_bytes == len(data)
    assert _output_files(workspace) == [destination], (
        "a boundary write left something other than the destination behind"
    )


def test_the_legacy_name_really_is_refused_in_that_very_parent(
    tmp_path: Path, ceiling: int
) -> None:
    """The negative control that makes the passing write above non-vacuous."""
    workspace, key, destination = _near_ceiling_workspace(tmp_path, ceiling)
    destination.parent.mkdir(parents=True, exist_ok=True)

    assert _visible(destination.parent) + 1 + LEGACY_TEMP_NAME_CHARS == ceiling + 1, (
        "the layout is not where the measured ceiling says the wall is"
    )
    assert not _try_exclusive_create(destination.parent, LEGACY_TEMP_NAME_CHARS), (
        "a 46-character name was accepted at this depth, so the write above "
        "would have passed without the repair"
    )
    assert _try_exclusive_create(destination.parent, LEGACY_TEMP_NAME_CHARS - 1), (
        "the negative control did not find the measured path-length switch"
    )

    receipt = TaskOutputArea(workspace).write(key, b"control", fsync=False)
    assert receipt.absolute_path.read_bytes() == b"control"


def test_the_seam_does_not_clobber_a_temp_name_it_did_not_create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cleanup claim, and its only direct witness."""
    workspace, key, destination = _plain_workspace(tmp_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Pin one id so the seam's name is knowable in advance. The refusal must
    # come from the real exclusive open, not from a substituted ``Path.open``.
    planted_id = new_id()
    monkeypatch.setattr(outputs_module, "new_id", lambda: planted_id)
    planted = destination.parent / _seam_temp_name(planted_id.hex)
    planted.write_bytes(b"not mine")

    with pytest.raises(FileExistsError):
        TaskOutputArea(workspace).write(key, b"x", fsync=False)

    assert planted.exists(), f"the refusing write deleted {planted.name}, a file it did not create"
    assert planted.read_bytes() == b"not mine", (
        "the refusing write both deleted and rewrote a file it did not create"
    )


def test_the_temp_name_still_carries_the_marker_the_older_witness_looks_for() -> None:
    """A marker change would blind ``test_workspace_boundaries.py``."""
    name = _seam_temp_name(new_id().hex)

    assert name.startswith(LEGACY_TEMP_MARKER), (
        f"the seam's temp name is now {name!r}, which the leftover sweep "
        "in tests/test_workspace_boundaries.py cannot see"
    )
    assert len(name) < LEGACY_TEMP_NAME_CHARS, (
        f"the temp name still spends {len(name)} characters, so the repair "
        "this file witnesses has not landed"
    )


def test_the_temp_name_draws_the_uuidv7_tail_not_the_head() -> None:
    """A head slice would make every write in one millisecond share a name."""
    hex_digits = "0123456789abcdef0123456789abcdef"

    assert outputs_module._temporary_name(hex_digits) == f"{LEGACY_TEMP_MARKER}89abcdef.tmp"


def test_a_past_budget_write_still_reports_the_os_refusal(tmp_path: Path, ceiling: int) -> None:
    """Direction A moves the wall; it does not invent a named path-budget refusal.

    The destination path can still be past the measured ceiling. This node
    accepts the current filesystem refusal or a canonicalisation refusal. A
    later batch that lands a named path-budget refusal can tighten this node.
    The ceiling is moved, not lifted.
    """
    workspace, key, destination = _near_ceiling_workspace(tmp_path, ceiling)
    area = TaskOutputArea(workspace)

    area.write(key, b"at the budget", fsync=False)
    assert destination.read_bytes() == b"at the budget", (
        "the in-budget write regressed, so the deeper write is not measuring the residual wall"
    )

    pad = len(key.split("/")[1])
    deeper_key = f"budget/{'a' * pad}/{'b' * 50}/result.bin"
    with pytest.raises((FileNotFoundError, WorkspaceError, OutputRefusedError)):
        area.write(deeper_key, b"past the budget", fsync=False)


def test_a_new_short_leftover_is_visible_to_the_older_sweep(tmp_path: Path, ceiling: int) -> None:
    """A planted short-name leftover is still discoverable by name."""
    workspace, key, destination = _near_ceiling_workspace(tmp_path, ceiling)

    TaskOutputArea(workspace).write(key, b"leftover", fsync=False)
    leftover = destination.parent / _seam_temp_name(new_id().hex)
    leftover.write_bytes(b"leftover")
    try:
        assert LEGACY_TEMP_MARKER in leftover.name, (
            "the marker check in tests/test_workspace_boundaries.py would not "
            "see a leftover from the repaired seam"
        )
        visible = {path.name for path in _sweep_output_area(workspace, destination)}
        assert leftover.name in visible, (
            "the repaired seam's leftover is not visible to the name-based sweep"
        )
    finally:
        leftover.unlink(missing_ok=True)


@pytest.mark.parametrize("extra_chars", [0, 1, 2])
def test_a_boundary_write_leaves_no_stray_temporary_file(
    tmp_path: Path, ceiling: int, extra_chars: int
) -> None:
    """Prefix-independent leftover sweep at the seam's boundary lengths."""
    workspace, key, destination = _near_ceiling_workspace(tmp_path, ceiling + extra_chars)

    TaskOutputArea(workspace).write(key, b"sweep", fsync=False)

    strays = sorted(path.name for path in _sweep_output_area(workspace, destination))
    assert strays == [], f"a boundary write left files behind: {strays}"


def test_the_ceiling_is_measured_at_run_time_and_bounded(ceiling: int) -> None:
    """The probe's answer is sane; 260 is not a remembered constant."""
    print(  # noqa: T201 - report, not product code
        f"MAX_PATH probe: visible ceiling = {ceiling}, os.name = {os.name!r}"
    )
    assert 100 <= ceiling <= 4096, (
        f"the probe returned {ceiling} on os.name={os.name!r}, which is not a "
        "path-length budget on any platform this suite runs on"
    )
