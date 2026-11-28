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
import queue
import subprocess
import sys
import threading
import time
import weakref
from pathlib import Path
from typing import IO, Any

import pytest

pytestmark = pytest.mark.e2e

#: The windows a kill can land in, as the injector names them.
BEFORE_TEMP_WRITE = "before_temp_write"
AFTER_TEMP_FSYNC = "after_temp_fsync"
AFTER_REPLACE = "after_replace"
AFTER_PUBLISH_LANDED = "after_publish_landed"

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
        # Armed only once the drill is inside the publication's own write.
        #
        # **Why the arming matters, and it is not decoration.** The rig's own
        # assembly writes the manifest through this same ``"xb"`` call, and
        # that write happens *before* the child prints its first marker. A
        # pause there parks the child before it has said anything at all, and
        # the parent's wait for that marker becomes a wait for a line the
        # child is 600 seconds away from. The window is named for the
        # *publication's* temp, so the pause is placed on the first temp
        # created after the drill arms itself.
        if args and args[0] == "xb" and os.environ.get("DRILL_ARMED") == "1":
            reach()
        return _original_open(self, *args, **kwargs)

    pathlib.Path.open = open_patch

elif WINDOW == "after_temp_fsync":
    import os as _os

    _original_fsync = _os.fsync

    def fsync_patch(fd):
        result = _original_fsync(fd)
        # Armed only once the copy has landed: the rig's own assembly and the
        # copy stage fsync too, and a kill before the publication stage would
        # land outside the window this drill names.
        if _os.environ.get("DRILL_ARMED") == "1":
            reach()
        return result

    _os.fsync = fsync_patch

elif WINDOW == "after_replace":
    # The copy's replace also goes through Path.replace; the sentinel only
    # fires when the replace's target is the publication's own name, so the
    # kill lands in the publication's window and not the copy's.
    _original_replace = pathlib.Path.replace

    def replace_patch(self, target):
        _original_replace(self, target)
        if pathlib.Path(target).name == "published.bin":
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
import os
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
# Arm the fsync window only now: the kill must land inside the
# publication's write, not in the rig's own assembly or the copy stage.
os.environ["DRILL_ARMED"] = "1"
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
                    + _drain(child.stderr, STDERR_DRAIN_SECONDS)
                )
            time.sleep(0.05)
        else:  # pragma: no cover
            raise AssertionError("the child never reached the window")
        assert child.poll() is None, "the child exited on its own; the kill proves nothing"
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

    **One pump per child, not one per call.** The helper is called more than
    once on the same child — the rewrite drill waits for ``RIG`` and then for
    ``FIRST`` — and two pumps on one pipe would take turns at the rows: the
    first pump could swallow the ``FIRST`` line before the second wait asked
    for it, and the second wait would then wait for a line that has already
    been read. So the queue belongs to the child and is found again on the
    next call.
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

    from labcairn.db.models import OperationRow, StageRow
    from labcairn.db.session import create_db_engine, create_session_factory

    db = tmp_path / "labcairn.db"
    engine = create_db_engine(db)
    session = create_session_factory(engine)()
    try:
        publication_stage_ids = set(
            session.execute(
                select(StageRow.stage_id).where(StageRow.name == "revision-publication")
            ).scalars()
        )
        rows = session.execute(select(OperationRow)).scalars()
        states = {row.state for row in rows if row.stage_id in publication_stage_ids}
    finally:
        session.close()
        engine.dispose()
    assert db.exists(), "the drill child never created the store"
    assert states <= {"attempting", "authorized"}, (
        f"the crash left the publication operation in states {states}; a kill "
        "during the write window must not leave a confirmed or failed completion"
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

    **What this watches.** The wait's deadline. The helper reads the child's
    stdout with a deadline, so a child that is alive and silent is reported:
    the helper says which marker it wanted, what the child had printed, what
    the child's exit status was, and what the child wrote to its stderr.

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
