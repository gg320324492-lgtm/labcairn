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
import queue
import subprocess
import sys
import threading
import time
import weakref
from pathlib import Path
from typing import IO, Any

import pytest
from drill_support import EDITED_BYTES, REWRITE_BYTES

pytestmark = pytest.mark.e2e

#: The windows a kill can land in during a rewrite, as the injector names them.
#: The names line up with the first-publish drill's so a reader can compare the
#: two matrices step by step; the rewrite-only window is the clobber, which by
#: definition cannot happen on a first publish.
BEFORE_REWRITE_TEMP_WRITE = "before_temp_write"
REWRITE_CLOBBER = "rewrite_clobber"
REWRITE_AFTER_TEMP_FSYNC = "after_temp_fsync"
REWRITE_AFTER_REPLACE = "after_replace"

#: How long the injector's pause holds the child before the parent kills it.
#:
#: The pause is deliberately longer than any healthy run: the point is to
#: park the child inside the window under test and let the parent kill it
#: there, so a wait that gave up before the pause would be giving up on the
#: child rather than on the injector.
INJECTOR_PAUSE_SECONDS = 600

#: How long the parent waits for a marker line before it gives up on the child.
#:
#: **Why this number.** A healthy drill child prints its first marker within a
#: few seconds — the drills that pass do so in 3.3 s to 4.3 s on this machine —
#: while the injector's own pause is 600 s. A wait that could reach 600 s
#: would be waiting on the injector rather than on the child, and a drill that
#: hangs would cost ten minutes to say so. 120 s is far above the healthy
#: path, far below the pause it has to interrupt, and it is the same ceiling
#: ``tests/test_fault_injection_e2e.py`` already gives a service to answer.
WAIT_TIMEOUT_SECONDS = 120.0

#: How long the parent waits for the child's stderr to end once the child's
#: stdout has ended. A child that is gone closes both at once; the ceiling is
#: there so that a stream some grandchild still holds open cannot turn the
#: failure into a hang of its own.
STDERR_DRAIN_SECONDS = 5.0

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
PAUSE = int(os.environ["DRILL_PAUSE_SECONDS"])


def reach() -> None:
    SENTINEL.write_text(WINDOW, encoding="utf-8")
    time.sleep(PAUSE)


if WINDOW == "before_temp_write":
    _original_open = pathlib.Path.open

    def open_patch(self, *args, **kwargs):
        # Armed only once the drill is inside the rewrite's own write.
        #
        # **Why the arming matters, and it is not decoration.** The rig's own
        # assembly writes the manifest through this same ``"xb"`` call, and
        # that write happens *before* the child prints its first marker. A
        # pause there parks the child before it has said anything at all, and
        # the parent's wait for that marker becomes a wait for a line the
        # child is 600 seconds away from. The window is named for the
        # *rewrite's* temp, so the pause is placed on the first temp created
        # after the drill arms itself.
        if args and args[0] == "xb" and os.environ.get("DRILL_ARMED") == "1":
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

from drill_support import EDITED_BYTES, MOMENT, REWRITE_BYTES, build_rig
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine, create_session_factory
from store_support import StoreEnv
from labcairn.workspace.outputs import TaskOutputArea

root = Path(sys.argv[1])
db = root / "labcairn.db"
upgrade_to_head(db)
engine = create_db_engine(db)
session = create_session_factory(engine)()
env = StoreEnv(db_path=db, engine=engine, factory=create_session_factory(engine), session=session)
rig = build_rig(env.store(), root / "workspace")
print("RIG", rig.loop.import_receipt.receipt_id, flush=True)

# The same key is written twice through the one write point: first to create
# the destination the ordinary way, then to rewrite it. The rewrite is the
# exact call whose windows the drills kill — the sequence publish_revision
# drives (TaskOutputArea.write, temp, fsync, os.replace) — minus the loop's
# receipt, which a loop cannot grant twice.
area = TaskOutputArea(rig.context.workspace)
area.write(rig.loop.publication_key, EDITED_BYTES)
print("FIRST", rig.publication_path().stat().st_size, flush=True)

# The rewrite. From here every armed window is inside the second write.
os.environ["DRILL_ARMED"] = "1"
area.write(rig.loop.publication_key, REWRITE_BYTES)
print("DONE", flush=True)
session.close()
"""


def _child_environment(inject_dir: Path, sentinel: Path, window: str) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(inject_dir),
        "DRILL_WINDOW": window,
        "DRILL_SENTINEL": str(sentinel),
        "DRILL_PAUSE_SECONDS": str(int(INJECTOR_PAUSE_SECONDS)),
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
                    + _drain(child.stderr, STDERR_DRAIN_SECONDS)
                )
            time.sleep(0.05)
        else:
            hard_kill(child)
            raise AssertionError("the drill child never reached its window")
        hard_kill(child)
        child.wait(timeout=60)


#: The stdout pump per drill child, so that two waits on one child do not
#: take turns at the pipe's rows. Keyed weakly: the pump's thread holds the
#: stream, not the child, and a finished drill must not be kept alive by the
#: table that remembers it.
_STDOUT_PUMPS: weakref.WeakKeyDictionary[subprocess.Popen[str], queue.Queue[str | None]] = (
    weakref.WeakKeyDictionary()
)


def _pump_lines(stream: IO[str]) -> queue.Queue[str | None]:
    """Read *stream* line by line on a thread and hand the lines over.

    A stream a live child still holds open never ends, so reading it on the
    calling thread is a way to hang. The pump is what makes the wait
    interruptible: the caller waits on the queue with a deadline instead of
    on the read. The queue's ``None`` is the stream's end.

    The thread is a daemon, so a stream that is never closed does not keep
    the interpreter alive: the run ends with the child, not with the pipe.
    """
    lines: queue.Queue[str | None] = queue.Queue()

    def pump() -> None:
        try:
            while True:
                line = stream.readline()
                if not line:
                    return
                lines.put(line)
        finally:
            lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    return lines


def _stdout_lines(child: subprocess.Popen[str]) -> queue.Queue[str | None]:
    """The queue carrying the child's stdout, one per child.

    **One pump per child, not one per call.** This file waits for ``RIG`` and
    then for ``FIRST`` on the *same* child, and two pumps on one pipe would
    take turns at the rows: the first pump could swallow the ``FIRST`` line
    before the second wait asked for it, and the second wait would then wait
    for a line that has already been read. So the queue belongs to the child
    and is found again on the next call.
    """
    pump = _STDOUT_PUMPS.get(child)
    if pump is None:
        assert child.stdout is not None
        pump = _pump_lines(child.stdout)
        _STDOUT_PUMPS[child] = pump
    return pump


def _drain(stream: IO[str] | None, timeout: float) -> str:
    """Whatever *stream* has produced by now, without waiting for its end.

    A child that is alive holds its stderr open, so reading it to the end
    would hang on exactly the failure this helper reports. What is wanted is
    what the child has *said*, so the read stops at the ceiling and the
    text so far is the answer.
    """
    if stream is None:
        return ""
    lines = _pump_lines(stream)
    collected: list[str] = []
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty:
            break
        if line is None:
            break
        collected.append(line)
    return "".join(collected)


def _child_status(child: subprocess.Popen[str]) -> str:
    """The child's exit status, said in words when it has not exited yet."""
    status = child.poll()
    if status is None:
        return f"the child was still running (pid {child.pid})"
    if status < 0:
        return f"the child was killed by signal {-status}"
    return f"the child exited with status {status}"


def _wait_for(
    child: subprocess.Popen[str],
    marker: str,
    timeout: float = WAIT_TIMEOUT_SECONDS,
) -> str:
    """Read the child's stdout up to a marker line, so rig output is not lost.

    **The deadline is the point of this helper.** A blocking ``readline()``
    waits for a line that a child which never prints one will never produce,
    and the child that never prints one is the child that is *alive* — parked
    inside the injector's pause, holding its stdout open. The parent then
    waits for a line that is 600 seconds away, and the run costs ten minutes
    to report nothing. So the read happens on a thread, the answer is
    collected with a deadline, and a child that has not spoken by then is a
    **failure that says what it saw** — the child's exit status and its
    stderr — rather than a hang.

    **What did not change.** The successful path is the one it always was:
    the same line, the same assertion, and the same text when the marker
    never appears and the child's stdout simply ends. Only the case where
    the child's stream *stays open* is new, and it is the case that used to
    hang.
    """
    assert child.stdout is not None
    lines: list[str] = []
    pending = _stdout_lines(child)
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                "the child produced no "
                + marker
                + " line within "
                + f"{timeout:g}s:\n"
                + "\n".join(lines)
                + "\nstatus: "
                + _child_status(child)
                + "\nstderr:\n"
                + _drain(child.stderr, STDERR_DRAIN_SECONDS)
            )
        try:
            line = pending.get(timeout=remaining)
        except queue.Empty:
            continue
        if line is None:
            raise AssertionError(
                "the child produced no "
                + marker
                + " line:\n"
                + "\n".join(lines)
                + "\nstderr:\n"
                + _drain(child.stderr, STDERR_DRAIN_SECONDS)
            )
        if line.startswith(marker):
            return line
        lines.append(line)


FIRST_PUBLISH_BYTES = EDITED_BYTES


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


#: The child that never speaks. It prints a line that is *not* the marker, and
#: then it holds its stdout open forever — the shape that used to hang the
#: parent, because a live child keeps the pipe open and a blocking read waits
#: for a line that will never come.
SILENT_CHILD = """\
import sys
import time

sys.stdout.write("READY BUT NOT THE MARKER\\n")
sys.stdout.flush()
time.sleep(3600)
"""


def test_the_wait_gives_up_on_a_child_that_never_prints_its_marker(tmp_path: Path) -> None:
    """A child that never speaks is a failure with a reason, not a hang.

    **What this watches.** The wait's deadline, in this file's own copy of
    the helper. The two drill files each carry their own helper — the
    duplicate is a known cost, recorded in the acceptance notes — so each
    copy needs its own witness: a witness in the other file would leave this
    one unwatched, and the hang this file had is the one that cost twenty
    minutes.

    **Why the call is made on a thread.** A witness that hangs is a witness
    that cannot fail. If the deadline were removed, the call below would
    block forever and the whole run would hang — which is the very failure
    this witness exists to catch, reproduced in the witness instead of
    caught by it. So the call runs on a thread, the witness waits for that
    thread with a deadline of its own, and a thread that is still running
    when that deadline passes is a **failure of the witness**: the helper
    did not give up, and the tree says so rather than hanging.

    **What the child's own state is.** The child is alive, holds its stdout
    open, and writes a line of its own to stderr. The failure must say all
    three: the child was still running, and the stderr is what the child
    said.
    """
    script = tmp_path / "silent.py"
    script.write_text(SILENT_CHILD, encoding="utf-8")
    child = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"},
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    outcome: list[BaseException | None] = []
    try:
        # A short deadline, so the witness costs seconds rather than minutes:
        # the property under test is that the deadline is *honoured*, not
        # what it happens to be.
        deadline_seconds = 2.0
        captured: list[BaseException | None] = []

        def wait_for_the_marker() -> None:
            try:
                _wait_for(child, "MARKER", timeout=deadline_seconds)
            except BaseException as error:
                captured.append(error)
            else:
                captured.append(None)

        waiter = threading.Thread(target=wait_for_the_marker, daemon=True)
        waiter.start()
        waiter.join(timeout=deadline_seconds + 30)

        assert not waiter.is_alive(), (
            "the wait is still blocked after its deadline of "
            f"{deadline_seconds:g}s, so the helper has no deadline and a child "
            "that never prints its marker hangs the parent instead of "
            "failing it"
        )
        outcome = captured
    finally:
        if child.poll() is None:  # pragma: no cover - only on a failure
            hard_kill(child)
        child.wait(timeout=30)

    assert outcome, "the wait returned without saying anything"
    failure = outcome[0]
    assert isinstance(failure, AssertionError), f"the wait did not fail; it returned {failure!r}"
    message = str(failure)
    assert "MARKER" in message, "the failure does not name the marker it waited for"
    assert "within 2s" in message, (
        f"the failure does not say the wait gave up on its deadline: {message!r}"
    )
    assert "READY BUT NOT THE MARKER" in message, (
        f"the failure does not report what the child had printed: {message!r}"
    )
    assert "still running" in message, (
        f"the failure does not report the child's exit status: {message!r}"
    )
    assert "stderr:" in message, f"the failure does not report the child's stderr: {message!r}"
