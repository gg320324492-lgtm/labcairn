# O6 — one unwired event stream stopped the whole service: mechanism found, fixed, witnessed

Anchors, printed live while this record was written:

| what | value |
|---|---|
| branch | `claude/sharp-pasteur-464783` |
| base commit (what everything was measured against) | `9f1f94b31fb858d3db96885825c5f9908253b94f` |
| `main` at the time of writing | `4855ea66d71ea8363aa578e7ca6b00e03efde7de` |
| fix commit | `102904819eee29fd37c574ab9a48f7ef9cb54d40` |
| starlette / anyio / fastapi / uvicorn / Python | 1.8.0 / 4.15.1 / 0.151.0 / 0.54.0 / 3.12.13 (MSC v.1944, AMD64) |
| platform | Windows 11 Pro, one machine, one run per measurement unless a row says otherwise |

**What this record is.** The selection stage found the defect and named it open:
`docs/acceptance/LC-P3-05-selection-measurement-2026-11-10.md` §9–§11 and the
operator-side record `E:\labcairn-local\phase3-g3-evidence\LC-P3-05\2026-11-10-environment-and-run-record.md`
§11a–§11i. That record deliberately **did not name a mechanism** — it refuted two
candidates and left the row open. This record names the mechanism, fixes it, and
witnesses it. Where this record's measurements sharpen or correct the selection
record's numbers, it says so here rather than editing that record's text; the one
change made there is the cross-reference in `docs/THREAT-MODEL.md` §6.2.

## 1. What the defect was, in one line

One `GET /events/stream` on a service with no event source — **even the short
`follow=false` form** — was followed by **no answer to anything**: `/health`,
`/tasks`, `/session`, `/papers`, `/docs`, `/openapi.json` all timed out at the
client's 8 s, while the TCP listener still accepted connections and the process
stayed alive. The selection record measured that shape (§11a: 0 / 10 mutations in
each of two runs; §11b: 0 / 6 with a plain HTTP client; §11g: **one** short stream
is enough).

## 2. The mechanism, as measured

The refusal was raised **after** the response had started, which turned it into a
**traceback the service wrote into its own output**, and a caller that captures
that output in a **pipe it does not read** has a pipe with a **capacity**. A loop
parked in a write to a full pipe is a loop that serves nothing.

Four measurements, each with the shape the selection record used:

**2.1 The dose that fills the pipe is smaller than one stream's traceback.**
The service's own output, counted by a reader that drains it continuously
(`E:\labcairn-local\tmp\o6probe\probe_volume.py`, arm with a real
`labcairn serve` against the real built `web/dist`):

| phase | bytes the service wrote | tracebacks |
|---|---|---|
| start-up | 944 | 0 |
| 5 ordinary reads (GET /health, /openapi.json, /session, /tasks, /plan) | **0** | 0 |
| **1 short unwired stream** | **6,205** | 2 |
| 8 short unwired streams | 49,640 | 18 |

An ordinary read costs the service nothing. One unwired stream costs it 6,205
bytes — two tracebacks, each through the whole ASGI stack.

**2.2 The pipe's capacity is a measured number, and it is smaller than 2.1.**
`E:\labcairn-local\tmp\o6probe\probe_capacity2.py`, a child process writing to a
`subprocess.PIPE` nobody reads, marker file written after the write:

```
N=  1024 fits=True   N=  2048 fits=True   N=  3072 fits=True   N=  4096 fits=True
N=  4608 fits=False  N=  5120 fits=False  N=  6144 fits=False  N=  8192 fits=False
BOUNDARY last_ok=4096 first_no=4608
```

A non-blocking `os.pipe()` on this machine measures the same **4,096** bytes.

**Correction this measurement forced on an earlier number in my own probing.**
The first capacity sweep (`probe_capacity.py`, and `probe_blocked.py` before it)
reported **8,192** by counting 4,096 per `os.write` **call**. `os.write` on a full
pipe performs a *partial* write and returns what it managed, so counting calls
overstates the pipe. The boundary measured by bytes actually accepted is **4,096**,
and the witness in §5 measures it that way (it sums `os.write`'s return values).
The defect's dose arithmetic does not change — 944 + 6,205 already exceeds 4,096 —
but the number a record quotes has to be the number the pipe held.

**2.3 A blocking write to a full pipe does not raise; it waits — and that is the
defect itself.** `probe_capacity.py`'s first version wrote in blocking mode and
*never returned*: measured `wrote 4096, raised: None, blocked: True`. A capacity
probe that writes the way the service writes reproduces the defect on itself. The
witness measures capacity with a non-blocking descriptor for exactly this reason.

**2.4 The differential — who reads the pipe — and the rescue.**
`E:\labcairn-local\tmp\o6probe\probe_pipe.py` runs the arrangement the selection
window's own probes used (the real console script, `serve --static-dir <built
dist>`, a real workspace, a real port) and varies **one** thing:

| arm | PHASE_A (no stream) | one short unwired stream | PHASE_B | after starting to drain |
|---|---|---|---|---|
| **nodrain** (`stdout=PIPE`, nothing reads it) | 5 / 5 | 200, 0 bytes | **0 / 5, all 8,015–8,032 ms timeouts** | **5 / 5, 0–16 ms (PHASE_C), and still 5 / 5 two seconds later (PHASE_D)** |
| **drain** (same pipe, drained from the start) | 5 / 5 | 200, 0 bytes (log 7,149 B, 2 tracebacks) | **5 / 5** | — |
| **devnull** (output to an unbounded sink) | 5 / 5 | 200, 0 bytes | **5 / 5** | — |

The `nodrain` arm reproduces §11a/§11b exactly, including the detail those sections
found hardest: **the stall does not end when the stream ends** — the pipe stays
full, and nothing recovers it. What does recover it is *starting to read*.

**Which is the mechanism.** A writer blocked in `write()` to a full pipe is not a
writer that is slow; it is a thread that is not running. The event loop is the
thing that accepts connections and serves every request in the process, and the
log write happens on it (`uvicorn`'s error path for an exception that reaches it
after the response started, and `BaseHTTPMiddleware`'s `raise app_exc`). So: the
listener answers, `/openapi.json` times out, the process is alive, the dose needed
is one stream, and no database or threadpool involvement is needed to explain any
of it. §11f's SQLite refutation and §11g's dose-response stand as measured.

**What the traceback is made of.** `starlette/_exception_handler.py:56` converts a
handled exception raised after the response started into
`RuntimeError("Caught handled exception, but response already started.")`;
`starlette/middleware/base.py:208` (`raise app_exc`) carries it out of the
guard middleware; `uvicorn`'s `run_asgi` then logs the whole chain
(`Exception in ASGI application`). That is the 6,205 bytes, and both halves of the
pair the selection record saw in its logs are there: the streaming task group's
`RuntimeError` and the second traceback through `base.py`. The service installs
`@app.middleware("http")` (`_guards`, `src/labcairn/api/app.py:389`), so every
request goes through it.

## 3. What the fix is

**Refuse an unwired stream before a response starts.** `get_event_stream`
(`src/labcairn/api/routes.py`) now looks at its source while the request still has
an answer it can be given:

```python
source = _event_source(request)
if isinstance(source, UnwiredEventSource):
    raise unwired_refusal()
```

and the refusal is the **same 403 and the same two fields** `GET /events` answers
with (`refusal_response` renders `ApplicationRefusedError` through the one handler
`_install_refusal_handlers` already installs). `events.py` gained the single source
of that sentence — `UNWIRED_REFUSAL_MESSAGE` and `unwired_refusal()` — so the two
sites that refuse cannot drift into two answers.

**What the fix does not do.** It does not wire the stream: `labcairn serve` still
passes no event source (`src/labcairn/cli/commands.py`), and `UnwiredEventSource.page`
still refuses rather than returning an empty page. It does not touch the guards:
`_check_origin`, the fetch-metadata rule and the session guard run in `_guards` in
the same order as before (`docs/THREAT-MODEL.md` §3.2), and the stream is still
covered by them — an unwired stream from a foreign origin is refused for the
origin, before the source is looked at. It does not change what a **wired** stream
does: the frames, the stream's own session and its `BEGIN IMMEDIATE` discipline are
untouched, and the existing witnesses that measure them (§5) stayed green.

**The harness half of the rule, unchanged and already held.** The other half of the
mechanism belongs to whoever captures the service's output, and the repository's
own G1 helper already keeps it: `tests/workbench_serve_support.py:232-234` writes
the service's log to a **file** rather than a pipe, with the reason spelled out —
*"a pipe nobody reads fills up and blocks the writer, which is a failure whose
cause is the harness and not the product."* That is why the G1 window measured the
unwired stream's *shape* (200, empty body, a logged traceback) and never its
*consequence*: its arrangement drains the output. The selection window's probes
used `stdout=PIPE` and read it only at the end.

## 4. The two witnesses

**4.1 The capacity witness.**
`tests/test_api_concurrency.py::test_one_unwired_event_stream_leaves_the_service_able_to_answer`
measures the service's **request capacity across an unwired stream**, in a
subprocess (a pytest process whose own stdout is an unread pipe is exposed to the
same hazard), with the service built the way the product builds it — `create_app`
over a real store, no event source, a real uvicorn on a real loopback port. It runs
**both** arrangements: the service's output drained (the control) and its output in
a pipe nobody reads (the arrangement the defect was measured in). It asserts:

- every ordinary read answered, on both sides of the dose, in both arrangements;
- **the dose could actually fill the pipe it was aimed at** — the probe measures
  the capacity (`_pipe_capacity`, non-blocking, summing `os.write`'s return values)
  and sizes the dose from it at the measured per-stream cost; a dose too small to
  overflow the pipe fails the test rather than passing quietly;
- what the service **costs itself to refuse**: the drained arm's byte count must be
  under `O6_LOG_BUDGET` (4,096). A refusal that reaches the client as a response
  costs nothing; a number over the budget means the service is producing a traceback
  again.

Measured on the fixed tree: pipe capacity 4,096 bytes, dose 5 (not capped), all five
streams answered **403**, **0 bytes** written by the service, **4 / 4** before and
after in both arrangements.

**4.2 The mutation checks.** Both were run on the committed tree with the fix
reverted, and the witness was re-greened from the commit afterwards (`git checkout
--`, no uncommitted work at the time).

| mutation | result |
|---|---|
| the entry refusal removed (the refusal raised inside `frames()` again) | **FAILED in 39.95 s** — undrained arm **0 / 4**, every read `TimeoutError` at 8,015–8,016 ms; the report named **stream 1** as where answering stopped (944 + 6,205 > 4,096). The drained arm stayed 4 / 4. |
| the route writes 5,000 bytes into its own output per unwired request, refusal otherwise intact | **FAILED in 65.39 s** — byte assertion reddened at **10,000 > 4,096**, while the capacity assertion stayed 4 / 4. |

The two assertions are therefore independent witnesses: the second mutation leaves
the service answering everything and is caught only by the byte count; the first
fills the pipe and is caught by the capacity assertion.

**4.3 Why this witness was not measured through the console script.** The selection
window's §11i records the editable-install shadow faithfully, and the shadow is real
— `E:\LabCairn\.venv\Scripts\labcairn.exe` is a compiled launcher whose `.pth` names
`E:\LabCairn\src`. The probes in §2 **were** run through it, and they are quoted
against a check: `git diff main..9f1f94b31fb858d3db96885825c5f9908253b94f --
src/labcairn/api/` is **empty**, and the six files' SHA-256 prefixes are identical
between the main checkout and this base commit — `routes.py 55d902ea…`,
`events.py fc9ba1f7…`, `app.py 5f9bc545…`, `guards.py a56d8b41…`,
`selection.py 6d409421…`, `session.py b3d090dd…`. So §2 measured the code this
record cites. The **witness** does not use that launcher at all: a child of
`tests/test_api_concurrency.py` imports this checkout, which is what the change
landed in.

## 5. What was re-measured in the tree, and what stayed green

Run locally (`--basetemp` at `E:\labcairn-local\tmp\bt-*`, `TEMP`/`TMP`/`TMPDIR`/
`MPLCONFIGDIR` outside the repository, `PYTHONPATH` pointed at this worktree's
`src` so the run measures this checkout and not the editable install's), statuses
read from the process and never from a pipe:

| file | result |
|---|---|
| `tests/test_api_concurrency.py` | **8 passed** in 20.60 s (7 existing + the new one) |
| `tests/test_workbench_live_service.py` | **1 passed** in 13.74 s (the wired stream: 200, frames, cursor) |
| `tests/test_ci_shard_coverage.py` | **16 passed** in 0.67 s (no new test file, so no cost re-measurement was owed) |
| `tests/test_workbench_serve_helper.py` | **11 passed, 2 skipped** in 57.12 s |
| ruff check / ruff format --check / mypy --strict | clean over `src/labcairn/api/` and the changed test files |

**The whole suite, once, on this machine.** `pytest -q` with
`--basetemp=E:\labcairn-local\tmp\bt-full-o6`, at head
`9f0edf2c9a1a89ca651f04f86a894c4b9bc6e37e`:

```
5 failed, 5068 passed, 26 skipped, 1161 warnings in 1925.62s (0:32:05)
```

The 26 skips are the browser rows and the provider-gated rows (`web/dist` is not built
here; no credential is named). **The 5 failures are not in the files this change
touched** — the diff from `9f1f94b` names eight files, none of them
`tests/test_no_reference_leakage.py` or `tests/test_outsider_path.py`. They were
attributed rather than assumed, and the attribution has two parts.

**One failure is this window's own measurement arrangement.** The wheel's clean-room
row failed on its own guard:

```
AssertionError: labcairn resolved to …, outside the clean venv at ….
The editable install of the working tree shadowed the wheel, so this assertion proved nothing.
```

The cause is mine: this window ran the suite with `PYTHONPATH=<worktree>/src` (the rule
for measuring a worktree rather than the editable install), and that test builds the
child's environment with `{**os.environ, "PYTHONIOENCODING": "utf-8"}`, so the path
leaked in and the import resolved to this checkout instead of the wheel. Re-running the
file **without** `PYTHONPATH` changes what fails: the shadowing assertion no longer
trips, and the row errors earlier, at the build.

**The other failures are this machine's network, measured and reproduced at the base
commit.** `uv` cannot reach PyPI here:

```
curl: (35) schannel: failed to receive handshake, SSL/TLS connection failed   (status 000)
uv: Failed to fetch: `https://pypi.org/simple/hatchling/` … tls handshake eof
```

so `uv build` (the reference-leakage probe's build) and the outsider walk's `uv sync`
both fail at the same place, in **both** trees. The control run at the base commit — a
detached worktree at `9f1f94b31fb858d3db96885825c5f9908253b94f`, no `PYTHONPATH` —
reports the same failure set:

| file | head `9f0edf2`, no PYTHONPATH | base `9f1f94b`, no PYTHONPATH |
|---|---|---|
| `tests/test_no_reference_leakage.py` | 102 passed, **8 errors** | 102 passed, **8 errors** |
| `tests/test_outsider_path.py` | **6 failed**, 11 passed | **6 failed**, 11 passed |

The walk's clone steps are `[ok]` in both (clone made, outside the repository, clean
tree, same commit); it stops at *"the README's `uv sync` succeeded"*. **The set is
compared, not the count**: the failure set at head equals the failure set at the base,
and both are pinned to a network condition this machine currently has. That is what
licenses saying these five are not this change's. §6 names the network as an open
condition rather than claiming a green suite here.

**The existing LC-P3-01 witness, and what its honesty now consists of.**
`test_the_event_stream_the_page_reads_is_unwired_in_the_service_the_cli_starts`
recorded a gap by asserting it: the stream **must** answer 200 with an empty body,
because that was what the service did. The fix changes the service's behaviour, so
the assertion that recorded the gap had to change — it was not made green by
pretending the stream is wired. It now measures the two halves of the new fact:
`GET /events` and `GET /events/stream` both answer **403** with
`not_implemented`. The stream is still unwired, and the test still says so; what
changed is that the refusal reaches the reader. The docstring names the old shape,
the measurement that made it dangerous, and this record.

**The two browser rows could not be re-measured here, and are named as open.**
`tests/test_workbench_real_browser.py` holds the panel half of the same finding:

- `test_the_page_makes_every_read_the_workbench_declares` asserted the page's
  stream read answered 200; it now asserts **403**, with a message that says a 200
  would mean the route had started the response again.
- `test_the_events_panel_reports_the_stream_live_on_a_service_that_has_none` was a
  gap witness asserting the *disagreement* — the panel's "is live" beside the
  service's own refusal. It is renamed
  `test_the_events_panel_says_the_stream_was_refused_on_a_service_that_has_none`
  and asserts the agreement: 403 on the wire, the panel reporting the stream
  **interrupted or disconnected**, **not** live, and the service's own
  `not_implemented` on `GET /events` still refused — because a panel that reported
  `live` on this service would be reporting an event source the service does not
  have.

Neither was executed: this machine's project venv has **no playwright** and there is
**no `web/dist`** (the file's own `_require_build` skip, and the CI shards install
neither). The assertions were derived from `web/src/api/events.ts` (a non-`ok`
stream response becomes an `ApiRefusal`; `ApiRefusal.reason` is the service's
`reason`) and `web/src/views/EventsView.tsx` (`reconnecting` → "The event stream
was interrupted (attempt N)…", `disconnected` → "The event stream is disconnected
after N attempts…"), and they are re-measurable with a build and a driver, not
carried as claims. **These two rows are the open items of this record.**

`docs/THREAT-MODEL.md` §6.2 carried the sentence this fix makes false ("the stream
route raises the same refusal *after* its own `200` … so a client receives a stream
that opens and ends with nothing in it"); it now states the measured 403-on-both-reads
shape, the O6 mechanism, the closed half, and the still-unwired half. The witness
that reads that section checks the §6.2 heading and the presence of
`/events/stream`, both of which still hold.

**The witness ledger, run against the two commits.** `scripts/witness_ledger.py
9f1f94b31fb858d3db96885825c5f9908253b94f e2b1a2faa4ea0f971cab661a6392da7faead7523`
reported **3,511 test functions before and 3,512 after**, and named every delta:

```
LOST -- 1 test function(s) that existed before and do not now:
  test_the_events_panel_reports_the_stream_live_on_a_service_that_has_none   (was in tests/test_workbench_real_browser.py)

ADDED -- 2 test function(s):
  test_one_unwired_event_stream_leaves_the_service_able_to_answer   (now in tests/test_api_concurrency.py)
  test_the_events_panel_says_the_stream_was_refused_on_a_service_that_has_none   (now in tests/test_workbench_real_browser.py)
```

**The one LOST row is this record's own rename, not a loss.** A composition that
renames a witness looks, to anything that matches names, exactly like a composition
that deletes one — which is the failure the ledger exists to catch, and it caught
this one. The row is not gone: it is the second ADDED entry, the same file and the
same three assertions (the page's stream read, the panel's sentence, the service's
`not_implemented`), with the assertion flipped from the disagreement to the
agreement §5 describes. Nothing else that existed before is missing.

## 6. What is still open

1. **The stream is not wired.** `labcairn serve` passes no event source. This fix
   makes the service honest about that; it does not give it a source. Wiring it is
   the owner's call and belongs to the packages that own the event reads.
2. **The browser rows (§5) are asserted but not executed** on this machine. A run
   with `pnpm install --frozen-lockfile && pnpm build` in `web/` and a playwright
   driver re-measures them. Until then the panel half of this finding is
   source-derived, not observed.
3. **This machine cannot reach PyPI, and two test files depend on it.** Measured:
   `curl` to `https://pypi.org/simple/hatchling/` fails at the TLS handshake (status
   000), and `uv` reports the same failure at `tls handshake eof`. That is why
   `tests/test_no_reference_leakage.py` (8 errors, at the build of its probe project)
   and `tests/test_outsider_path.py` (6 failed, at the walk's `uv sync`) fail here in
   **both** the head tree and the base tree — and why the clean-Windows and
   installed-wheel claims those two files witness are **not currently re-measurable on
   this machine at all**. A run with network, or a warm `uv` cache, re-measures them;
   nothing in this record claims they pass.
4. **One deviation in this window's own measuring, recorded.** The whole-suite run
   (§5) was started at `4afb82969bcc0a69dadce5cc823a57499655a6d4`, and the tree was
   committed twice while it ran — `e2b1a2faa4ea0f971cab661a6392da7faead7523` and
   `9f0edf2c9a1a89ca651f04f86a894c4b9bc6e37e`, both touching only `docs/acceptance/`,
   which no test reads. The project's rule is *do not change the tree while a
   measurement runs*, and that rule was broken here. The §5 suite numbers belong to the
   tree as it stood when the run started, with a documentation-only change landing
   underneath them; the re-runs that decide the failure set (§5's table) were run
   afterwards with the tree clean at `9f0edf2`, and the attribution rests on those.
5. **The harness rule is a rule, not a guard.** A caller that puts the service's
   output in a pipe it never reads can still park *any* service that writes
   anything — the product's structured logging is not the only writer (uvicorn's
   own error path is another). What the fix removes is the service's **traceback
   per unwired request**, i.e. the fuel the selection window measured; a service
   handed an undrainable sink is still a service that can be blocked by its own
   logging. `src/labcairn/api/` does not own how a host captures its output, and
   no guard here pretends otherwise.
6. **The capacity numbers belong to this machine and to the versions in the anchor
   table.** 4,096 bytes is this machine's anonymous-pipe capacity; Linux's default
   is an order of magnitude larger, which is why the witness measures the capacity
   it works against (and requests a bounded pipe where the platform takes the
   request) rather than carrying 4,096 or 8,192 forward. A future run on another
   platform re-measures the capacity and the dose, and the report says which it was.

## 7. Files this record's change touched

- `src/labcairn/api/routes.py` — the entry refusal, and the reason written where
  the refusal is raised.
- `src/labcairn/api/events.py` — `UNWIRED_REFUSAL_MESSAGE`, `unwired_refusal()`,
  `UnwiredEventSource`'s contract restated (its own refusal is what any caller that
  asked it directly gets, and it is what `GET /events` answers with).
- `tests/test_api_concurrency.py` — the capacity witness, the capacity probe, and
  the file docstring's second property.
- `tests/test_workbench_serve_helper.py`, `tests/test_workbench_real_browser.py` —
  the two gap rows, re-measured into the new shape.
- `docs/THREAT-MODEL.md` §6.2 — the sentence the fix made false, corrected.
- this record.

`src/labcairn/application/`, `src/labcairn/editing/`, `web/` product code and
ADR-0021 were not touched: the defect and its fix are both entirely in the service.
