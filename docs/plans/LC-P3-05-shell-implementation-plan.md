# LC-P3-05 — Electron shell implementation plan

**Anchors:** 3 — every converted pointer below carries the words it cites.

**Date:** 2026-11-10. **Status:** a plan, not an implementation record. This
document writes no product code, adds no dependency and claims no ticket
status. It is the implementation stage's opening inventory for `LC-P3-05`
(`docs/plans/PHASE_3-work-orders.md` §10), after the owner's Electron
selection and ADR-0023's acceptance on 2026-11-10.

**Decision it implements.** ADR-0023 (`docs/adr/ADR-0023-desktop-shell-integration-keeps-the-served-origin.md`)
decides the integration shape: the shell wraps **the origin the service
already serves**. The selected framework is **Electron** — the only candidate
buildable on this machine as it stands (`docs/acceptance/LC-P3-05-selection-measurement-2026-11-10.md`
§3, §11). These are different decisions: the owner chose the framework; the
ADR chose the shape. This plan implements both and does not re-open either.

**File ownership.** This plan writes **no file under `src/labcairn/`**. The
shell lives in its own directory (proposed: `desktop/`, decided in T01), with
its own package manifest. Product code under `src/labcairn/` changes only if a
step below says so explicitly and the owner approves it; no step in this plan
does. `web/` preload/IPC work is scoped by §0's file-ownership table and the
owner's dispatch split — the plan names the seams, it does not pre-empt another
window's files.

## 1. Inputs this plan rests on

| Input | Where the measurement is | What the plan takes from it |
| --- | --- | --- |
| The four-candidate selection, Electron measured buildable (357 MB `dist/`, Electron 45.2.3 / Chromium 156.0.8078.80 / Node 24.22.2) | selection record §3–§6, §11 | Electron is the framework; its footprint is a recorded cost, not a surprise. |
| The integration shape and the three guards (bind address, origin check, session token) | selection record §7, §11; ADR-0023 "Decision"; `docs/THREAT-MODEL.md` §3.2 | The window loads the served origin; `file://`, custom schemes, main-process API routing and `--origin` widening are all out. |
| `file://` and `app://` refusals, and the main-process token finding | selection record §7.1–§7.3 | Security baseline §5 and the same-origin witness (AC-1, AC-4). |
| O6: an unread pipe parks its writer; 4,096-byte capacity, 6,205 bytes per unwired stream; the service-side fix and witness | `docs/acceptance/o6-event-stream-stall-2026-11-10.md` §2, §4, §6.5 | The hard rule of §3 and its witness design. The fix removed the traceback fuel; it did **not** make an undrained pipe safe. |
| `labcairn serve`'s shape: `--host` (loopback only), `--port`, `--origin`, `--static-dir`, `--json` (`ServiceStarting` carries `host`, `port`, `origin`, `origins`, `task_id`, `token_path`, `static_dir`) | `src/labcairn/cli/commands.py:2116-2211`, `src/labcairn/cli/models.py:293-315` | The exact child command and the readiness signal. |
| The dev arrangement: Vite on `127.0.0.1:5173` with a proxy that changes no origin header; `DEVELOPMENT_ORIGINS` already answers to it | `web/vite.config.ts`, `src/labcairn/cli/commands.py:2091-2113` | Dev mode §4.2 reuses the arrangement that exists. |
| The built bundle names no remote host and the service serves it from its own origin | `web/src/api/bundle.test.ts`, `src/labcairn/api/app.py:448` — `app.mount("/", StaticFiles(directory=static_dir, html=True), name="workbench")` (`--static-dir` mount) | AC-1 and AC-7; a shell dependency is read the same way. |
| New dependency is an owner decision (§0 rule 4); every boundary claim witness-backed (§0 rule 5); a new test file needs three registrations (§3 rule 3) | `docs/plans/PHASE_3-work-orders.md` §0, §3 | T01's approval gate; §6's acceptance criteria; T02–T07's registration obligations. |

Numbers cited here are those records' numbers at their measured commits. A
value that can change is re-measured at the commit that carries the
implementation, not carried forward (CLAUDE.md, "Claims are measured, not
asserted").

## 2. The minimum integration shape

One main process, one window, one child service. No framework inside the
renderer, no second HTTP server, no product logic in Node.

```
Electron main process
  |-- spawns: labcairn serve --host 127.0.0.1 --port <p> --static-dir <web/dist>
  |             (stdout + stderr DRAINED from the first byte -- §3)
  |-- waits for readiness: the ServiceStarting JSON line, then GET /health 200
  |-- BrowserWindow.loadURL(http://127.0.0.1:<p>/)
  |     webPreferences: nodeIntegration false, contextIsolation true,
  |                     sandbox true, no raw ipcRenderer (§5)
  |-- preload: a narrow, enumerable API surface; NO session token, NO fetch proxy
  |-- on exit: stop the child, then close the window
```

The built workbench is served by `labcairn serve --static-dir <web/dist>` from
the service's own origin. The window loads that origin. Therefore page and API
are same-origin, the allow-list gains nothing, the session token stays in the
page's own module state exactly as `web/src/api/session.ts` arranges it, and a
mutation without the token is still refused `401 session_required`. **Nothing
under `src/labcairn/api/` changes to admit the shell.** That is the measured
property of ADR-0023, not a convenience.

Port selection: the shell asks the OS for a free loopback port (or takes an
explicit `--port` in dev) and passes it to `serve`; it must not assume 8000 is
free. The service's `--json` output is the authority for what it actually
bound — `ServiceStarting.host/port/origin` — and its `origins` field is what
the same-origin witness reads back. The token path in `ServiceStarting` names a
file; the shell neither reads nor copies the token value.

**Explicitly out of shape** (each measured as costing the boundary in the
selection record): loading `file://` or `app://` pages; making main-process
`net.fetch` calls on the workbench's behalf; widening `--origin` for the
shell; serving the bundle from Electron; embedding a Python runtime in the
renderer. O3 of the selection record (how a Python runtime ships) is a
packaging question answered in §4.1, not a reason to move the HTTP boundary.

## 3. Hard rule: stdout and stderr are drained from the first byte

> **Rule.** Any pipe the shell opens to the child service's `stdout` or
> `stderr` has a reader attached **before the child can write**, and that
> reader keeps reading until the pipe closes. There is no code path that
> creates `PIPE` and reads it only at the end, or only on error. Redirecting
> both streams to a log file is equally acceptable and is the simpler
> arrangement. What is forbidden is an unread pipe.

**Why this is a hard rule and not a note.** O6 measured the whole chain
(`docs/acceptance/o6-event-stream-stall-2026-11-10.md` §2): the unwired stream
route raised *after* its `200` + `text/event-stream` headers, so the refusal
became a traceback the service wrote into its own output — **6,205 bytes per
short stream**, two tracebacks, against 0 bytes for an ordinary read; the
caller's `subprocess.PIPE` held **4,096 bytes** on this machine; a writer
parked in a full pipe is an event loop that serves nothing. The three-arm
differential there is the decisive evidence: the **nodrain** arm answered
`0 / 5` ordinary reads (all 8 s timeouts) after one stream and `5 / 5` as soon
as draining started (PHASE_C), while the **drain** arm over the identical
service and identical stream answered `5 / 5`. The service-side fix refuses
the stream before its headers and is witnessed
(`tests/test_api_concurrency.py::test_one_unwired_event_stream_leaves_the_service_able_to_answer`,
two counter-mutations). **The harness half survives the fix** (O6 record
§6.5): uvicorn's own error path and the product's structured logging are
writers too, so *any* service handed an undrainable sink can be parked by its
own output. `tests/workbench_serve_support.py:232-234` already states the rule
in the repository's own G1 helper — it writes the service log to a file, with
the reason spelled out. The shell inherits that rule as a host, not as a
Python test.

**Implementation requirements.**

1. Both streams are captured (pipes with permanent readers, or a log file).
   `stdio` is never `inherit` into a console nobody reads, and never left at a
   default that hides a pipe.
2. Readers are attached at spawn time: `on('data')` handlers or equivalent
   exist before the child writes its first byte. No "read at exit", no
   `await stream.toString()` after readiness.
3. The drained bytes go to a bounded, rotating log file outside the
   repository (the product's own temp convention: `E:\labcairn-local\` on this
   machine; no corpus text, no token value is logged). A shell that drains
   into an unbounded in-memory buffer has swapped one leak for another.
4. An unhandled reader error, or a reader that stops, is a shell-level error:
   the window shows a diagnostic and the service child is stopped. It is not
   swallowed.
5. A crash in the main process must not leave the child alive (§4.3); a child
   that outlives its window holds the port and the workspace lock.
6. On Windows the child is started in its own process group so the whole tree
   can be terminated (ADR-0022's platform-conditional rule: one reachable
   body per platform, no constants from the wrong platform).

**Witness design for the rule (AC-3).** A property that is asserted and not
watched is not held. The witness must be a **control pair** in the shape of
O6's, not a check that the source mentions `data` handlers. It has three
arms, because the O6 fix removed the service's traceback fuel and a witness
that depends on that fuel would not be re-measurable:

- **Arm A (the physical property).** The shell's real supervisor module (T02)
  spawns a **test-only writer child**, injected through a spawn-command seam
  that the packaged build never exposes. The child is a small loopback HTTP
  responder of the shell's own test fixtures: on a request it writes a
  witness-controlled number of bytes to **its own stdout**, then answers. So
  the writer that can be parked is the child's own event loop — the same
  shape O6 measured — not the test process. The dose exceeds the pipe's
  **measured** capacity: the witness probes capacity with non-blocking
  `os.write`, summing the return values (O6 witness §4.1's `_pipe_capacity`;
  a dose too small to overflow fails the test rather than passing quietly).
  The capacity is re-measured on the runner that runs it — 4,096 is this
  machine's number, not a constant.
- **Arm B (the control pair).** The same child and the same dose run twice:
  **drained** (the production reader shape) answers every request within a
  bounded time before, during and after the dose; **undrained** (a debug-only
  harness switch, never reachable from a packaged build) **reproduces the
  stall** — requests time out while the child stays alive. That undrained arm
  is what proves the dose could actually fill the pipe. A witness that stays
  green in both arms has not measured anything.
- **Arm C (the real service, as a regression control).** A real
  `labcairn serve` against a real temporary workspace with a synthetic task,
  on an OS-chosen loopback port, started by the production supervisor with
  **no injection**: `GET /health`, `GET /tasks`, `POST /task/select` (with the
  token) and one guard-free endpoint (`/openapi.json`) all answer before and
  after a bounded burst of ordinary reads. This arm does not re-create O6's
  stall — the service-side witness already holds that — it holds the claim
  that the production path itself drains.
- **Counter-mutation.** Removing or deferring the reader in the production
  supervisor must make Arm A's drained arm go red. The mutation is run on a
  committed tree and reverted with `git checkout --` only after confirming no
  uncommitted work. A mutation that does not take effect is not evidence
  either way.
- The test file, if new, owes the three registrations (`pytestmark` gate
  class, `.github/ci-shards.json`, `tests/evaluation/manifest.py`) and a
  runner-measured cost — §3 rule 3; a local timing is not a runner cost. The
  window reports the package/version/licence/lockfile change to the owner
  under §0 rule 4 before editing any manifest.

## 4. Two run modes and the process lifecycle

### 4.1 Packaged mode (the delivered application)

- The installer carries: the Electron app, the **built** `web/dist` bundle,
  and the product's Python runtime. **O3 is answered here by a measured trial,
  not by this plan**: the three arrangements the selection record names are a
  frozen service, a bundled interpreter and a sidecar. The trial's first
  obligation is the O5 finding — a PyInstaller freeze of this product died at
  import until `PYDANTIC_DISABLE_PLUGINS=1`, because `logfire`'s pydantic
  plugin reads source text at runtime. The implementation window measures the
  chosen arrangement against the **installed** product's graph and records
  which it picked and why; this plan does not pick it.
- The main process resolves the packaged `labcairn` entry point at runtime
  (an absolute path inside the installation, never a name resolved from
  `PATH`), the workspace path from the user's data directory, and the built
  bundle's path inside the resources. No `cwd` guessing: interpreters load
  code from their own directory and the current directory.
- Signing is **not** produced (deferred behind `W28`, `LC-P3-00` §6). Support
  limits and signing status are recorded in the clean-Windows drill, not
  claimed here.

### 4.2 Dev mode

- `pnpm dev` keeps Vite on `127.0.0.1:5173`; the service runs on its own
  loopback port with `--json` and (optionally) no `--static-dir`, because the
  page comes from Vite. The workbench's proxy already sends API requests to
  the service and changes no origin header; `DEVELOPMENT_ORIGINS` already
  admits that page's two spellings.
- The shell's dev switch loads `http://127.0.0.1:5173` **only in dev** and
  never in a packaged build; a test asserts the packaged build's load URL is
  the service's own origin (AC-1). The dev switch is a one-line difference in
  the URL the window loads, not a second integration shape.
- Dev mode drains stdout/stderr exactly as packaged mode does. There is no
  "dev is exempt" branch.
- Dev mode does not build an installer, does not sign, and does not touch
  `src/labcairn/`.

### 4.3 Lifecycle: exit, crash, port occupancy

| Event | Required behaviour | Witness |
| --- | --- | --- |
| Normal window close / `app.quit` | The main process stops the service child (graceful signal, then a bounded timeout, then forced termination of the process group on Windows), waits for its `exit`, then exits. No orphan. | AC-2: after the window closes, the port is free and no child process holds the workspace. |
| Main-process crash / uncaught exception | The child is still stopped. A supervisor hook (`before-quit`, `will-quit`, plus an `uncaughtException` handler that does its job and exits) covers the paths; the child is never left behind on an error path. | AC-2's crash arm: kill the main process and assert the child is gone. |
| Service child exits early (startup refusal: bad workspace, no current task, invalid bind) | The window does not show a blank page. The last drained output and the child's exit code are surfaced in a diagnostic; startup fails closed and the shell exits. | AC-2's refusal arm: a bad `--static-dir` / bad workspace is measured to produce a visible refusal and no window loading a foreign page. |
| Service child crashes after readiness | The window shows a disconnected state; the shell does **not** silently respawn into a second workspace lock. A user-visible restart action is the only restart path. | AC-2's crash-after-ready arm. |
| Chosen port already occupied | The shell asks for another free loopback port **before** spawn and re-checks the `ServiceStarting` fields; it never binds a port it did not ask for and never assumes a foreign listener is its own service. A foreign listener is a refusal, not a page to load. | AC-2's occupancy arm: a deliberate listener on the chosen port must not be loaded as the workbench. |
| Second instance | Single-instance lock: a second launch focuses the existing window and does not start a second service. | AC-2's second-instance arm. |

Every readiness wait has a bounded timeout and a failure path. The readiness
signal is the service's own `--json` `ServiceStarting` line **plus** a
`GET /health` 200 from that exact origin — a port answering is not a service
that is ready (O6 measured a live TCP listener that answered nothing).

### 4.4 Packaging and CI

- The Electron dependency, its version, licence and lockfile change are
  **reported to the owner for approval under §0 rule 4 before any manifest is
  edited** (T01). **Approved 2026-11-10 by the owner** (dialog: Electron
  45.2.3 / MIT / `shell/pnpm-lock.yaml` adopted; the plan's T01 gate is
  discharged). The selection record measured `electron@45.2.3` with a 1.2
  MB npm stub whose binary arrives at first `require` (~100 MB class, 31 s on
  this machine) — a build job must be able to reach that channel, and that is
  an owner/CI fact, not a surprise discovered by a runner.
- No CI workflow is changed by this plan. If the implementation adds a shell
  build step or a test file, the shard costs come from a runner run and the
  three registrations are completed in the same batch (§3 rule 3).
- The clean-Windows drill (install → launch → upgrade → uninstall → rollback
  preserving user data), support limits and signing status remain §3.6 row 3
  and §3.7's obligation; this plan's AC-6 names the evidence fields but does
  not perform the drill.

## 5. Security baseline

Everything here is a property to witness, not a checkbox to tick (§0 rule 5).

1. **`nodeIntegration: false` and `contextIsolation: true`** on every
   `BrowserWindow` and every `webContentsView`; `sandbox: true` for the
   renderer. Electron's own guidance makes the pair mandatory; a test reads
   the actual `webPreferences` object the window was constructed with, not a
   constant declared in a config file (a constant nobody passes is dead code).
2. **External navigation and external links are refused.** `setWindowOpenHandler`
   and `will-navigate` deny anything whose origin is not the service origin
   (dev: the Vite origin); external `http(s)` links are not opened in the
   app's own window. No `shell.openExternal` on unvalidated URLs. A witness
   drives a foreign URL and asserts refusal (AC-4).
3. **The allow-list is unwidened.** No `--origin` is passed for the shell; the
   `ServiceStarting.origins` field and `GET /health` are read back. A witness
   asserts the loaded page's origin equals `ServiceStarting.origin` (AC-1).
4. **The session token never crosses the preload/IPC boundary.** The preload
   exposes an enumerable, argument-validated surface that carries no token,
   no raw `ipcRenderer` and no general-purpose fetch proxy; IPC handlers
   validate the sender's **origin**, not its URL (selection record §7.3,
   ADR-0023 "Contracts" entry 3). The token stays in the page's module state.
   A witness asserts a native API surface cannot read the token and that a
   mutation without it is refused 401 (AC-4).
5. **No COM / ProgID / UI automation path to WPS or Word** becomes available
   through the shell (work orders §3.3, §0 rule 2). A candidate whose only
   DOCX integration is automation is a recorded finding, not an exception.
6. **The built bundle still names no remote host.** `web/src/api/bundle.test.ts`
   watches the built bytes; the shell's own dependencies are read the same way
   (ADR-0023 "Contracts" entry 7, AC-7).
7. **The service stays loopback-bound.** The shell passes `--host 127.0.0.1`
   and does not expose the port; `labcairn serve` itself refuses any other
   bind address (`src/labcairn/cli/commands.py:2297` — `def _check_host(host: str, *, as_json: bool) -> None:`, `_check_host`, called at
   `src/labcairn/cli/commands.py:2189` — `_check_host(host, as_json=as_json)`). The session guard's three layers stay exactly where
   `docs/THREAT-MODEL.md` §3.2 puts them.
8. **No secrets or corpus text in the tree.** No token value, no pilot corpus
   text, no credential file is written into the repository by any step; the
   drained log lives outside the tree (§3). Signing: deferred, recorded, not
   produced.

## 6. Acceptance criteria

Each criterion names the witness that fails when the property is broken. This
is the minimum set; the implementation window may add more, and every new
test file owes §3 rule 3's registrations.

| # | Criterion | Witness shape |
| --- | --- | --- |
| AC-1 | The packaged window loads the service's own origin; page and API are same-origin; no `--origin` was added; `file://` and custom schemes are never loaded. | A live service started by the shell's real supervisor; assert `loadURL` equals `ServiceStarting.origin`, assert `ServiceStarting.origins` has no shell-added entry, and assert the dev-build URL is rejected in a packaged configuration. A counter-mutation swapping in `file://` makes it red. |
| AC-2 | Process lifecycle: normal exit, main-process crash, child crash after readiness, startup refusal, port occupancy and second instance all behave as §4.3's table. | One integration witness per arm, using an OS-chosen port and a real child; the occupancy arm's foreign listener is a deliberate socket, not a stub. |
| AC-3 | stdout/stderr are drained from the first byte, and the drained arrangement keeps the child answering under a measured pipe-filling dose. | The three arms and counter-mutation of §3's witness design: the injected writer's drained/undrained control pair, the real-service regression control, and a reader-removal mutation that makes the drained arm red. |
| AC-4 | Security baseline holds: `nodeIntegration` off, `contextIsolation` on, external navigation refused, token unreachable from the native layer, mutation without token 401. | A witness that reads the constructed window's `webPreferences`, drives a foreign navigation, and inspects the preload surface's exposed names; plus the live HTTP 401 check from inside the shell. |
| AC-5 | Dev and packaged modes both start, and dev's Vite origin is the only difference. | Two startup runs; a test asserting the packaged build's load URL and the dev switch's explicit opt-in. |
| AC-6 | Clean-Windows drill recorded end to end (install, launch, upgrade, uninstall, rollback preserving user data), with commit, package hash, OS and host versions; support limits and signing status recorded. | The dated acceptance record under `docs/acceptance/` (§3.6 row 3). Not performed by this plan. |
| AC-7 | The built bundle and the shell's dependencies name no remote host. | `web/src/api/bundle.test.ts` extended or mirrored for the shell's own dependency set; a positive control (an introduced remote host) makes it red. |
| AC-8 | No COM/ProgID/UI-automation route to a DOCX host exists in the shell's surface. | A static witness over the shell's declared native surface with a positive control, plus the §0 rule 2 review in the acceptance record. |

**Gate honesty.** Local runs are evidence until a runner says otherwise
(CLAUDE.md). A whole-suite run uses a `--basetemp` outside the repository,
its own `TEMP`/`TMP`/`TMPDIR`/`MPLCONFIGDIR`, `COLUMNS=200`, `PYTHONPATH`
pointed at the worktree's `src` when measuring a worktree, and the status is
read from the process, not a pipe. Two pytest runs never share one
`--basetemp`. After any merge, `python scripts/witness_ledger.py <before>
<after>` is run. No CI is started and no pull request is opened by the
implementation window; the batch lands locally and the owner decides when one
run is spent (CLAUDE.md).

## 7. Task breakdown — each step is one independently committable unit

The steps are ordered by dependency, but each leaves a clean, reviewable
tree: one commit, one subject, no half-written module. **No step edits
`src/labcairn/`.** The decomposition holds nine steps.

| Step | Subject | Files it owns (proposed) | Done when |
| --- | --- | --- | --- |
| T01 | **Approval gate and layout.** Re-check `docs/adr/` numbering live (the §3.4 table's numbering discipline, with ADR-0022 taken by §3 rule 3a's platform-conditional rule) and report to the owner the Electron package, exact version, licence and lockfile change under §0 rule 4; record the chosen `desktop/` layout and the file-ownership map. | `docs/plans/LC-P3-05-shell-implementation-plan.md` (an addendum recording the decisions), a new `desktop/README.md` | The owner's approval is recorded, the layout is named, and no manifest has been edited before it. |
| T02 | **Service supervisor and the drain rule.** Spawn `labcairn serve` with an OS-chosen loopback port, `--json`, `--static-dir`, absolute paths; attach stdout/stderr readers at spawn; parse `ServiceStarting`; readiness = JSON + `GET /health` 200, with a bounded timeout. | new `desktop/src/service-supervisor.*`, its unit tests | §3's requirements 1–4 are in the module and the module starts a real service from a scratch workspace. |
| T03 | **The drain witness (AC-3).** The injected-writer control pair, measured dose, undrained arm's stall, the real-service regression arm and the counter-mutation; the three registrations for any new test file, with runner-measured costs. | new `desktop/src/service-supervisor.test.*` (or `tests/test_shell_service_supervisor.py`), a test-only writer fixture, plus the three registration files if a `tests/` file is added | The drained arm answers every read, the undrained arm stalls, the real service answers, and removing the reader makes the drained arm red. |
| T04 | **Window and same-origin load (AC-1).** `BrowserWindow` with the §5 baseline, load `ServiceStarting.origin`, deny foreign navigation and new windows; `setWindowOpenHandler`/`will-navigate` wired. | new `desktop/src/main.*`, `desktop/src/window.*` | A real window loads the served workbench and the same-origin/allow-list assertions pass; a `file://` counter-mutation is caught. |
| T05 | **Preload/IPC tightening (AC-4).** Enumerable, validated preload surface with no token, no raw `ipcRenderer`, no fetch proxy; sender-origin validation; the live 401 mutation check. | new `desktop/src/preload.*`, `web/src` preload/IPC types only if the owner's dispatch assigns them, and their tests | The token-reachability and 401 witnesses pass; the exposed names are asserted, not inferred. |
| T06 | **Lifecycle (AC-2).** Graceful stop, forced process-group termination on Windows, crash paths, startup refusal diagnostics, port re-selection and foreign-listener refusal, single-instance lock. | `desktop/src/main.*`, `desktop/src/service-supervisor.*`, their tests | Every arm in §4.3's table has a passing witness and leaves no orphan. |
| T07 | **Dev mode (AC-5).** The explicit dev switch loading the Vite origin, with the packaged URL unchanged; both modes drain. | `desktop/src/config.*`, `desktop/package.json` scripts (after T01's approval), dev docs | Two startup runs pass and the packaged build refuses the dev URL. |
| T08 | **Packaging, runtime arrangement and bundle reading (AC-7, O3/O5).** Measure the frozen-service / bundled-interpreter / sidecar choice against the installed product graph; produce the installer configuration; read the shell's dependency set for remote hosts. | `desktop/` packaging config, a dated measurement note under `docs/acceptance/` | The chosen arrangement starts in a packaged build, O5's import finding is answered by measurement, and the remote-host witness has a positive control. |
| T09 | **Clean-Windows drill and acceptance record (AC-6, AC-8).** Install → launch → upgrade → uninstall → rollback preserving user data, support limits, signing status, the §0 rule 2 review, and the witness ledger after any merge. | new `docs/acceptance/LC-P3-05-clean-windows-drill-<date>.md`, board row update with its evidence | The record names commit, package hash, OS and host versions, and the row moves in the same commit as its evidence. |

**What is deliberately not a step.** No product-code change under
`src/labcairn/`, no `web/` feature work beyond the preload/IPC seam, no
signing, no CI workflow edit performed without a runner-measured cost, no
push, no pull request, no CI run. Those are owner/gate decisions recorded in
CLAUDE.md and §0 of the work orders.

## 8. Open items inherited, with their owners

- **O1/O2/O3/O5/O7/O8** of the selection record §10 are the implementation
  stage's opening inventory; O6 is closed (see §1, and the cross-reference in
  that record's §10). O2 (Tauri's buildability) stays an owner/machine
  decision, not a step here.
- **O4** (CI gate cost) and §3 rule 3's costs belong to a runner run, not to a
  local timing.
- The two browser rows in the O6 record §5 were skipped on this machine (no
  playwright, no `web/dist`); the implementation window re-measures them where
  a build and a driver exist, rather than carrying them as claims.
- The real advisor sample and the trial logistics are `LC-P3-08`'s; §3.5 of
  the work orders keeps 05 independent of them.
- Signing remains behind `W28`. Support limits are recorded, not expanded.

**Number check performed for this plan.** Before writing, `ls docs/adr/` was
re-read: `ADR-0023-desktop-shell-integration-keeps-the-served-origin.md` is
still the highest ADR number in the tree (ADR-0022 is the previous one). That
is the re-check the §3.4 table asks for — the table whose own parenthetical
places ADR-0022 at §3 rule 3a's platform-conditional rule — and this plan
issues no new ADR number. ADR-0023's status change from Proposed to Accepted
is the only status change this plan's window makes.
