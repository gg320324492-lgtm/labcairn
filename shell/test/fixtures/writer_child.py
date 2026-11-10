"""The drain witness's writer child (test fixture, not product code).

A small loopback HTTP responder with one dangerous habit: on ``GET /ping`` it
writes a witness-controlled number of bytes to **its own stdout** before it
answers. The writer that can be parked is this child's own request handler —
the same shape ``docs/acceptance/o6-event-stream-stall-2026-11-10.md`` §2
measured (the service wrote its traceback into its own output) — not the test
process.

**Why Python and not Node.** The stall depends on a *synchronous blocking*
write: Node's ``process.stdout`` buffers pipe writes asynchronously and its
event loop keeps serving, so a Node writer would shrug off a full pipe and the
undrained arm would prove nothing. Python's ``sys.stdout.flush()`` blocks in
the write when the pipe is full, which parks this single-threaded handler — and
parks the whole responder with it. That is the mechanism O6 measured.
"""

from __future__ import annotations

import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1])
DOSE = int(sys.argv[2])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - the stdlib's own name
        if self.path == "/ping":
            # The dose. A blocking flush against a pipe nobody reads parks
            # this handler, and with it the server.
            sys.stdout.write("x" * DOSE)
            sys.stdout.write("\n")
            sys.stdout.flush()
            body = b'{"served": true}'
        else:
            body = b'{"status": "ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """stderr stays quiet: the dose is stdout, and a witness that mixes
        two writers cannot tell which one filled the pipe."""


def main() -> None:
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    sys.stdout.write(f"writer-ready {PORT}\n")
    sys.stdout.flush()

    def stop(_signum, _frame) -> None:
        """The group-ask: close the listener, exit 0, prove the ask worked."""
        server.server_close()
        sys.stdout.write("writer-stopped\n")
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
