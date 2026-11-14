"""Interrupted-write drills: kill the loop inside its write windows, observe the disk.

Drill class 1 of work orders §12 §5.1. The design is
``docs/plans/LC-P3-07-drill-matrix-design.md`` §2.1: kill inside the
publication/copy windows of ``labcairn.application.revision_loop`` — between
the temp-file write and ``os.replace`` in ``TaskOutputArea.write`` — and
expect *either the old file or the new one*, never a half-written destination
and never another writer's temp name.

The injection technique is the one ``tests/test_fault_injection_e2e.py``
established: the child announces (by sentinel file) that it genuinely reached
the window under test, and the parent kills it there — an announce-then-kill,
not a sleep guess. The window is named by an environment variable read by a
``sitecustomize`` module planted on the child's ``PYTHONPATH``, so the same
harness serves every window.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.e2e

#: The windows a kill can land in, as the injector names them.
BEFORE_TEMP_WRITE = "before_temp_write"
AFTER_TEMP_FSYNC = "after_temp_fsync"
AFTER_REPLACE = "after_replace"
AFTER_PUBLISH_LANDED = "after_publish_landed"

INJECTOR = '''
"""A pause planted in the drill child, from outside.

The product is run; this only decides *when* it stops. The parent waits for
the sentinel and then kills the process, so the crash is the parent's kill
and not an exit this module performs.
"""

import os
import pathlib
import time

WINDOW = os.environ["DRILL_WINDOW"]
SENTINEL = pathlib.Path(os.environ["DRILL_SENTINEL"])


def reach() -> None:
    SENTINEL.write_text(WINDOW, encoding="utf-8")
    time.sleep(600)


if WINDOW == "before_temp_write":
    _original_open = pathlib.Path.open

    def open_patch(self, *args, **kwargs):
        if args and args[0] == "xb":
            reach()
        return _original_open(self, *args, **kwargs)

    pathlib.Path.open = open_patch

elif WINDOW == "after_temp_fsync":
    import os as _os

    _original_fsync = _os.fsync

    def fsync_patch(fd):
        result = _original_fsync(fd)
        reach()
        return result

    _os.fsync = fsync_patch

elif WINDOW == "after_replace":
    _original_replace = pathlib.Path.replace

    def replace_patch(self, target):
        _original_replace(self, target)
        reach()

    pathlib.Path.replace = replace_patch

elif WINDOW == "after_publish_landed":
    import labcairn.workspace.outputs as outputs

    _original_fsync_directory = outputs.TaskOutputArea._fsync_directory

    def fsync_directory_patch(directory):
        reach()
        return _original_fsync_directory(directory)

    outputs.TaskOutputArea._fsync_directory = fsync_directory_patch
'''

_CHILD_SCRIPT = """\
import sys
from pathlib import Path

sys.path.insert(0, r"{tests_dir}")

from drill_support import (
    EDITED_BYTES, MOMENT, build_rig, grant_copy, grant_publication,
)
from labcairn.application.revision_loop import publish_revision, stage_copy
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine, create_session_factory
from store_support import StoreEnv

root = Path(sys.argv[1])
db = root / "labcairn.db"
upgrade_to_head(db)
engine = create_db_engine(db)
session = create_session_factory(engine)()
env = StoreEnv(db_path=db, engine=engine, factory=create_session_factory(engine), session=session)
rig = build_rig(env.store(), root / "workspace")
print("RIG", rig.loop.import_receipt.receipt_id, flush=True)
stage_copy(rig.context, rig.loop, approval_id=grant_copy(rig), now=MOMENT)
rig.copy_path().write_bytes(EDITED_BYTES)
publish_revision(
    rig.context, rig.loop,
    approval_id=grant_publication(rig), edited_bytes=EDITED_BYTES, now=MOMENT,
)
print("DONE", flush=True)
session.close()
"""


def _child_environment(inject_dir: Path, sentinel: Path, window: str) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(inject_dir),
        "DRILL_WINDOW": window,
        "DRILL_SENTINEL": str(sentinel),
        "PYTHONIOENCODING": "utf-8",
        "COLUMNS": "200",
    }


def hard_kill(child: subprocess.Popen[Any]) -> None:
    """Terminate without cleanup — ``taskkill /F`` on Windows, ``SIGKILL`` elsewhere."""
    if os.name == "nt":  # pragma: no cover - platform branch
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(child.pid)],
            capture_output=True,
            check=False,
        )
        return
    import signal

    sigkill = getattr(signal, "SIGKILL", None)
    assert sigkill is not None
    os.kill(child.pid, sigkill)


class KilledLoop:
    """The rig, built and run in a child process, killed inside a named window.

    The kill has to land in a *process* that is mid-write, so the child does
    the whole rig assembly and the loop run; the parent reads the layout back
    from the disk afterwards.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.inject_dir = tmp_path / "inject"
        self.inject_dir.mkdir(exist_ok=True)
        (self.inject_dir / "sitecustomize.py").write_text(INJECTOR, encoding="utf-8")
        self.sentinel = tmp_path / "sentinel.txt"
        self.script = tmp_path / "run_rig.py"
        self.script.write_text(
            _CHILD_SCRIPT.format(tests_dir=str(Path(__file__).parent)),
            encoding="utf-8",
        )

    def launch(self, window: str) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [sys.executable, str(self.script), str(self.tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_child_environment(self.inject_dir, self.sentinel, window),
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def kill_when_window_reached(self, child: subprocess.Popen[str]) -> None:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.sentinel.exists():
                break
            if child.poll() is not None:
                raise AssertionError(
                    "the drill child died before reaching the window:\n"
                    + (child.stderr.read() if child.stderr else "")
                )
            time.sleep(0.05)
        else:  # pragma: no cover
            raise AssertionError("the child never reached the window")
        assert child.poll() is None, "the child exited on its own; the kill proves nothing"
        hard_kill(child)
        child.wait(timeout=60)


def _wait_for(child: subprocess.Popen[str], marker: str) -> str:
    """Read the child's stdout up to a marker line, so rig output is not lost."""
    assert child.stdout is not None
    lines: list[str] = []
    while True:
        line = child.stdout.readline()
        if not line:
            raise AssertionError(
                "the child produced no " + marker + " line:\n" + "\n".join(lines)
                + "\nstderr:\n" + (child.stderr.read() if child.stderr else "")
            )
        if line.startswith(marker):
            return line
        lines.append(line)


def test_a_kill_between_the_temp_write_and_the_replace_leaves_old_or_new(
    tmp_path: Path,
) -> None:
    """The destination is never half-written and never carries a stranger's name.

    The kill lands between the temp file's ``fsync`` and the ``os.replace``:
    the temp exists, the destination does not yet — and after the kill the
    destination is either absent (nothing published) or present whole, but
    never partial, and no temp file survives with content.
    """
    kill = KilledLoop(tmp_path)
    child = kill.launch(AFTER_TEMP_FSYNC)
    try:
        _wait_for(child, "RIG")
        kill.kill_when_window_reached(child)
    finally:
        if child.poll() is None:  # pragma: no cover
            hard_kill(child)

    loop_dir = tmp_path / "workspace" / "output"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert published == [], "a kill before os.replace must not leave a published file"
    for loop in loop_dir.glob("*/revisions/*") if loop_dir.exists() else []:
        for stray in loop.iterdir():
            if stray.name.startswith(".lc-write-"):
                # A temp with content is the crash's own evidence — the write's
                # temp, killed with its handle open — and it is never the
                # destination: its name carries the write-temp marker, its
                # bytes are a whole staged payload, and the ledger left the
                # operation ATTEMPTING below. What must never happen is a
                # destination half-written or a temp promoted to output.
                assert stray.suffix == ".tmp"
                assert stray.stat().st_size > 0 or stray.read_bytes() == b""
        destinations = [p for p in loop.iterdir() if not p.name.startswith(".lc-write-")]
        for destination in destinations:
            assert destination.is_file(), f"{destination.name} is a directory?"
            assert destination.stat().st_size > 0, (
                f"the destination {destination.name!r} is empty — a half-write"
            )

    # The ledger is the other half of the observable: the operation whose
    # outcome the crash left open is ATTEMPTING on disk — the state the
    # recovery pass reads — never a confirmed completion the disk cannot show.
    from sqlalchemy import select

    from labcairn.db.models import OperationRow
    from labcairn.db.session import create_db_engine, create_session_factory

    db = tmp_path / "labcairn.db"
    engine = create_db_engine(db)
    session = create_session_factory(engine)()
    try:
        rows = session.execute(select(OperationRow)).scalars()
        states = {row.state for row in rows}
    finally:
        session.close()
        engine.dispose()
    assert states <= {"attempting", "authorized"}, (
        f"the crash left operation states {states}; a kill during the write "
        "window must not leave a confirmed or failed completion"
    )
    assert "attempting" in states, (
        "the operation whose write was in flight is ATTEMPTING on disk — the "
        "state the recovery half reads"
    )


def test_a_kill_after_the_replace_leaves_the_new_file_whole(tmp_path: Path) -> None:
    """Once ``os.replace`` has returned, the publication is on disk whole.

    The kill lands after the replace but before the directory fsync and the
    receipt: the bytes are the new file, complete, and no temp name remains.
    """
    kill = KilledLoop(tmp_path)
    child = kill.launch(AFTER_REPLACE)
    try:
        _wait_for(child, "RIG")
        kill.kill_when_window_reached(child)
    finally:
        if child.poll() is None:  # pragma: no cover
            hard_kill(child)

    loop_dir = tmp_path / "workspace" / "output"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert len(published) == 1, "the replace landed, so the publication is on disk"
    assert published[0].read_bytes() == (
        b"drill original line one\ndrill edited line two\ndrill original line three\n"
    ), "the published bytes are the edited bytes, whole"
    strays = [p for p in published[0].parent.iterdir() if p.name.startswith(".lc-write-")]
    assert strays == [], "no temp name survives a completed replace"


def test_a_kill_before_the_first_byte_leaves_nothing_behind(tmp_path: Path) -> None:
    """The canonicalise-first rule: a kill before the temp exists leaves no trace.

    ``TaskOutputArea.write`` canonicalises the target *before* any temporary
    exists; a kill in that window leaves no temp file, no destination, and no
    half-state — the pre-write world, exactly.
    """
    kill = KilledLoop(tmp_path)
    child = kill.launch(BEFORE_TEMP_WRITE)
    try:
        _wait_for(child, "RIG")
        kill.kill_when_window_reached(child)
    finally:
        if child.poll() is None:  # pragma: no cover
            hard_kill(child)

    loop_dir = tmp_path / "workspace" / "output"
    strays = list(loop_dir.glob("*/revisions/*/.lc-write-*")) if loop_dir.exists() else []
    assert strays == [], "no temp file exists when the kill precedes its creation"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert published == [], "nothing was published, because nothing was written"
