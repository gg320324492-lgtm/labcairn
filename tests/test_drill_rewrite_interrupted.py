"""Rewrite kill-window drills: the destination already exists when it dies.

Companion to ``tests/test_drill_interrupted_writes.py``, which kills the loop
inside the write windows of a **first** publish — a destination that does not
exist yet. The P3 final audit (F-A1, mutation M6) measured the gap this file
closes: a crash in the middle of a **rewrite** — the target file already
holds the previous publication when the kill lands — had no witness at all.

The contract under drill is unchanged from the first-publish case and is the
one ``TaskOutputArea.write`` claims: a crash leaves the destination either
the old content or the new content, never a half-written file, and any temp
left behind is a whole staged payload under the write-temp marker, never a
destination. A rewrite makes this observable in a way a first publish cannot
be: the old content is on disk to be found.

The injection is the announce-then-kill technique the interrupted-write
drills established: the child plants a ``sitecustomize`` module that
annotates the window under test and blocks there; the parent waits for the
sentinel and then kills the process, so the crash is the parent's kill and
not an exit the child performs. The kill is hard — ``taskkill /F`` on
Windows, ``SIGKILL`` elsewhere — so no ``finally`` block on the child's side
gets a say in what the disk ends up holding.
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

#: The windows a kill can land in during a rewrite, as the injector names them.
#: The names line up with the first-publish drill's so a reader can compare the
#: two matrices step by step; the rewrite-only window is the clobber, which by
#: definition cannot happen on a first publish.
BEFORE_REWRITE_TEMP_WRITE = "before_temp_write"
REWRITE_CLOBBER = "rewrite_clobber"
REWRITE_AFTER_TEMP_FSYNC = "after_temp_fsync"
REWRITE_AFTER_REPLACE = "after_replace"

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

elif WINDOW == "rewrite_clobber":
    # A rewrite opens the destination's parent for the temp file. The sentinel
    # fires on the first ``xb`` open that happens while the rewrite is armed,
    # i.e. before this write's temp is created — the moment a clobbering
    # mutation would strike the existing destination.
    _original_open = pathlib.Path.open

    def open_patch(self, *args, **kwargs):
        if args and args[0] == "xb" and os.environ.get("DRILL_ARMED") == "1":
            reach()
        return _original_open(self, *args, **kwargs)

    pathlib.Path.open = open_patch

elif WINDOW == "after_temp_fsync":
    import os as _os

    _original_fsync = _os.fsync

    def fsync_patch(fd):
        result = _original_fsync(fd)
        # Armed only once the first publication has landed: the rig's own
        # assembly, the copy stage and the first publication all fsync, and a
        # kill before the rewrite would land outside the window this drill
        # names.
        if _os.environ.get("DRILL_ARMED") == "1":
            reach()
        return result

    _os.fsync = fsync_patch

elif WINDOW == "after_replace":
    # The copy's replace and the first publication's replace also go through
    # Path.replace; the sentinel only fires when the replace's target is the
    # publication's own name *and* the rewrite is armed, so the kill lands in
    # the rewrite's window and not an earlier one's.
    _original_replace = pathlib.Path.replace

    def replace_patch(self, target):
        _original_replace(self, target)
        if (
            pathlib.Path(target).name == "published.bin"
            and os.environ.get("DRILL_ARMED") == "1"
        ):
            reach()

    pathlib.Path.replace = replace_patch
'''

_CHILD_SCRIPT = """\\
import os
import sys
from pathlib import Path

sys.path.insert(0, r"{tests_dir}")

from drill_support import (
    EDITED_BYTES, MOMENT, build_rig, grant_copy, grant_publication,
    run_loop_to_publication,
)
from labcairn.application.revision_loop import publish_revision
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

# First publication: the destination is created the ordinary way, so the
# drill's kill lands on a genuine rewrite of an existing file.
run_loop_to_publication(rig)
print("FIRST", rig.publication_path().stat().st_size, flush=True)

# The rewrite. From here every armed window is inside the second write.
os.environ["DRILL_ARMED"] = "1"
publish_revision(
    rig.context, rig.loop,
    approval_id=grant_publication(rig),
    edited_bytes=b"rewrite payload line one\\nrewrite payload line two\\n",
    now=MOMENT,
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


class KilledRewrite:
    """The rig, built and published once in a child, killed mid-rewrite.

    The kill has to land in a *process* that is mid-write, so the child does
    the rig assembly, the first publication and the rewrite; the parent reads
    the layout back from the disk afterwards.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.inject_dir = tmp_path / "inject"
        self.inject_dir.mkdir(exist_ok=True)
        (self.inject_dir / "sitecustomize.py").write_text(INJECTOR, encoding="utf-8")
        self.sentinel = tmp_path / "sentinel.txt"
        self.script = tmp_path / "run_rewrite.py"
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
        else:
            hard_kill(child)
            raise AssertionError("the drill child never reached its window")
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
                "the child produced no "
                + marker
                + " line:\n"
                + "\n".join(lines)
                + "\nstderr:\n"
                + (child.stderr.read() if child.stderr else "")
            )
        if line.startswith(marker):
            return line
        lines.append(line)


REWRITE_BYTES = b"rewrite payload line one\nrewrite payload line two\n"
FIRST_PUBLISH_BYTES = (
    b"drill original line one\ndrill edited line two\ndrill original line three\n"
)


def _kill_during(window: str, tmp_path: Path) -> None:
    """Run the child to its rewrite window and hard-kill it there."""
    kill = KilledRewrite(tmp_path)
    child = kill.launch(window)
    try:
        _wait_for(child, "RIG")
        _wait_for(child, "FIRST")
        kill.kill_when_window_reached(child)
    finally:
        if child.poll() is None:  # pragma: no cover
            hard_kill(child)


def _assert_whole_file(destination: Path) -> None:
    """The destination is one of the two whole payloads, never a hybrid."""
    content = destination.read_bytes()
    assert content in (FIRST_PUBLISH_BYTES, REWRITE_BYTES), (
        "the destination after the kill is neither the old content nor the "
        "new content — a half-written rewrite surfaced"
    )


def test_a_kill_before_the_rewrite_temp_exists_leaves_the_old_file_whole(
    tmp_path: Path,
) -> None:
    """A kill before the rewrite's temp exists cannot have touched the target.

    The canonicalise-first rule holds on the rewrite path too: the
    destination still holds the first publication, whole, and no temp name
    exists.
    """
    _kill_during(BEFORE_REWRITE_TEMP_WRITE, tmp_path)

    loop_dir = tmp_path / "workspace" / "output"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert len(published) == 1, "the first publication is on disk"
    _assert_whole_file(published[0])
    assert published[0].read_bytes() == FIRST_PUBLISH_BYTES, (
        "a kill before the rewrite's temp exists leaves the old file untouched"
    )
    strays = [p for p in published[0].parent.iterdir() if p.name.startswith(".lc-write-")]
    assert strays == [], "no temp name exists when the kill precedes its creation"


def test_a_kill_at_the_clobber_moment_leaves_the_old_file_whole(
    tmp_path: Path,
) -> None:
    """The rewrite-clobber window: the moment a clobbering write would strike.

    This is M6's window. A mutation that writes half the new bytes straight
    into the destination before the temp file is created lands *here*; the
    assertion is that the destination is still one of the two whole payloads.
    The product does not write through the destination at this point, so the
    witness holds — and it now holds by observation rather than by absence of
    a drill.
    """
    _kill_during(REWRITE_CLOBBER, tmp_path)

    loop_dir = tmp_path / "workspace" / "output"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert len(published) == 1, "the first publication is on disk"
    _assert_whole_file(published[0])
    assert published[0].read_bytes() == FIRST_PUBLISH_BYTES, (
        "a kill at the clobber moment leaves the old file untouched"
    )


def test_a_kill_between_the_rewrite_temp_write_and_the_replace_leaves_old_or_new(
    tmp_path: Path,
) -> None:
    """The destination is old-whole or new-whole, and a surviving temp is whole.

    The kill lands between the rewrite's temp ``fsync`` and the
    ``os.replace``. The destination may still be the old file (the replace
    had not happened) or may not exist as far as this window is concerned —
    but since this is a rewrite, "the old file" is the whole first
    publication. A temp that survives the kill carries the whole staged
    payload under the write-temp marker, never the destination's name.
    """
    _kill_during(REWRITE_AFTER_TEMP_FSYNC, tmp_path)

    loop_dir = tmp_path / "workspace" / "output"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert len(published) == 1, "the publication is on disk"
    _assert_whole_file(published[0])
    for stray in published[0].parent.iterdir():
        if stray.name.startswith(".lc-write-"):
            assert stray.suffix == ".tmp"
            assert stray.read_bytes() == REWRITE_BYTES, (
                "a surviving temp is the whole staged rewrite payload"
            )


def test_a_kill_after_the_rewrite_replace_leaves_the_new_file_whole(
    tmp_path: Path,
) -> None:
    """Once the rewrite's ``os.replace`` has returned, the new file is whole.

    The kill lands after the replace but before the directory fsync and the
    receipt: the bytes are the rewrite's, complete, and no temp name remains.
    """
    _kill_during(REWRITE_AFTER_REPLACE, tmp_path)

    loop_dir = tmp_path / "workspace" / "output"
    published = list(loop_dir.glob("*/revisions/*/published.bin")) if loop_dir.exists() else []
    assert len(published) == 1, "the replace landed, so the publication is on disk"
    _assert_whole_file(published[0])
    assert published[0].read_bytes() == REWRITE_BYTES, (
        "the published bytes are the rewrite's, whole"
    )
    strays = [p for p in published[0].parent.iterdir() if p.name.startswith(".lc-write-")]
    assert strays == [], "no temp name survives a completed replace"
