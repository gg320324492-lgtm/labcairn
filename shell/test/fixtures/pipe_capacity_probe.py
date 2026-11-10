"""How many bytes a fresh pipe holds before a write stops fitting.

The witness sizes its dose from this number, so the number is measured on the
machine that runs the witness rather than carried from the record — 4,096 is
this machine's value, and a Linux pipe defaults to an order of magnitude more.

The implementation is the one ``tests/test_api_concurrency.py``'s
``_pipe_capacity`` proved out on 2026-11-10, kept shape-identical on purpose:

* **non-blocking** — a blocking probe would reproduce the stall on itself and
  hang; ``BlockingIOError`` is what says the pipe is full;
* **summing what ``os.write`` returned** — a partial write returns the count it
  managed, and adding 1024 per call would report a capacity the pipe never
  held.
"""

from __future__ import annotations

import os

read_fd, write_fd = os.pipe()
try:
    os.set_blocking(write_fd, False)
    fitted = 0
    while True:
        try:
            fitted += os.write(write_fd, b"x" * 1024)
        except BlockingIOError:
            break
finally:
    os.close(read_fd)
    os.close(write_fd)

print(fitted)
