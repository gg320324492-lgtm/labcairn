"""Measure the capacity of the pipe the supervisor's own spawn created.

**Why this measures the child's own stdout and not an anonymous pipe.** The
witness has to size its dose against the pipe the *child is actually handed* —
the one `node:child_process.spawn` creates with `stdio: ['ignore', 'pipe',
'pipe']`. An anonymous `os.pipe()` on this machine holds 4,096 bytes
(`docs/acceptance/o6-event-stream-stall-2026-11-10.md` §4), and the witness's
first run measured the spawn arrangement at **114,688 fits / 131,072 stalls**:
a dose sized from 4,096 would have overflowed nothing, and an "undrained arm"
that never stalls is a witness that measured nothing.

**The shape is the one `tests/test_api_concurrency.py`'s `_pipe_capacity`
proved out**, kept deliberately:

* **non-blocking** — a blocking probe reproduces the stall on itself and hangs;
  `BlockingIOError` is what says the pipe is full;
* **summing what `os.write` returned** — a partial write returns the count it
  managed, and adding 1,024 per call would report a capacity the pipe never
  held (the mistake the O6 record §4 names).

Nobody reads the pipe during the measurement — that is the point — so the
answer comes back through a marker file, not through the full pipe.
"""

from __future__ import annotations

import os
import sys

stdout_fd = sys.stdout.fileno()
os.set_blocking(stdout_fd, False)

fitted = 0
while True:
    try:
        fitted += os.write(stdout_fd, b"x" * 1024)
    except BlockingIOError:
        break

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(str(fitted))
sys.exit(0)
