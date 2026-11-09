# LC-P3-05 — the desktop shell candidates, measured before one is chosen

**Date:** 2026-11-10. **Type:** dated selection-and-measurement record for the
selection stage of `LC-P3-05` (`docs/plans/PHASE_3-work-orders.md` §10), Phase 3
G3. It records what was measured, what each measurement showed, which option
the record adopts, and what a candidate's refusal would mean. It is **not** an
acceptance record and claims no ticket status.

**What this stage is, and what it is not.** §3.2 scopes `LC-P3-05` as two
stages in one ticket, in order: a selection and measurement stage, then
implementation of the chosen shell. This record is the first stage only. It
writes **no product code**, edits no manifest, touches no CI workflow and no
registration file, and **does not move the board's `LC-P3-05` row** — rows move
when the owner dispatches implementation. The shell choice belongs to the owner;
what this record owes the owner is measurements, not a verdict dressed as one.

## Anchors, printed live while this record was written

| Ref | Value |
| --- | --- |
| the commit the measurements were taken against | `26f816b2ecaf03a3d62b914d685edd4f54e0356b` — "the real sample is picked from the corpus registry" (2026-11-09 23:49:12 +0800) |
| local `main` | `26f816b2ecaf03a3d62b914d685edd4f54e0356b` (equal to the above) |
| `origin/main` | `571e4346a03374e166f3ab67d0067eb0e632dd52` (merge of PR #153; **local `main` is ahead of it** — this record was written before the batch's push) |
| the window's branch | `claude/quizzical-chatterjee-602cfe` (a scratch ref, per the branch rule) |
| working tree at anchor time | `git status --porcelain` 0 lines |
| newest ADR in the tree at draft time | `ADR-0022-platform-conditional-code-keeps-one-reachable-body.md`; **`ADR-0023` re-checked as free** (`ls docs/adr/ADR-0023*` → none), as §3.4 requires |

A record cannot cite the commit that first carries it.

**Machine, and what that word means here.** Windows 11 Pro 10.0.26300 x64 — the
development machine, not a runner, and not a clean environment. Every number
below is a **local** measurement; none is runner-measured. `TEMP`, `TMP`,
`TMPDIR` and `MPLCONFIGDIR` were pinned to `E:\labcairn-local\tmp\p305-selection`
(outside the repository) for every command; every scratch artifact lives under
`E:\labcairn-local\p305-selection\`. No push, no pull request and no CI run was
started by this window.

**The evidence that carries the commands.** The full command list, the raw
outputs, the probe sources and the per-run JSON live **outside the tree** at
`E:\labcairn-local\phase3-g3-evidence\LC-P3-05\2026-11-10-environment-and-run-record.md`
(the standing decision that machine-environment evidence stays operator-side,
`LC-P3-00` §7). Rows below name their section there as `§n`. Nothing temporary
entered the repository.

---

## 1. What the surface actually is

Execution plan §3's sentence names what a shell must carry: *reuse of the
workbench, preload and IPC tightening, navigation, file opening, runtime
lifecycle and local API session boundaries*. The last of those is not a shell
feature — it is the boundary `docs/THREAT-MODEL.md` §3 draws, and a shell either
preserves it or spends it. So the measurements were arranged around one
question per candidate: **what does this candidate do to the three request
guards** — the bind address, the origin check, the session token
(`guards.py`, `app.py:196-238`)?

Two properties of the existing arrangement were measured first, because they are
what a candidate is compared against:

| Property | Measured |
|---|---|
| the workbench bundle names no remote host | the build is 269 KB over 3 files (`index.html` 0.60 kB, CSS 3.81 kB, JS 267.72 kB — 80.61 kB gzipped), built in 2.7 s; the bundle witness `web/src/api/bundle.test.ts` allows exactly `www.w3.org` and `react.dev` and checks the **built** bytes, not the source (§6) |
| the token never enters a cookie, a URL or storage | `web/src/api/session.ts` holds it in a module variable; the service answers a mutation only on a presented `Bearer` token, measured directly: POST without → refused, POST wrong token → refused, POST with the minted token → applied, GET → permitted either way (§7) |

## 2. The four candidates, in one line each

| Candidate | One-line verdict | Rests on |
|---|---|---|
| **Electron** | **Buildable here today, and expensive:** the binary downloads and runs (0.63 s to a windowless run), but it ships its own Chromium and Node — a 357 MB `dist/` with a 238 MB `electron.exe` — on top of an installed product that is already a 514 MB `site-packages`; and its two natural page origins are refused by the product's own `--origin` grammar | §3, §9, §10 |
| **Tauri** | **Not buildable here at all:** a Rust compiler is present and a working Windows link environment is not, and the candidate's own CLI says the same thing about this machine; the dependency graph it would bring resolved to 403 crates before a single object file was linked | §2, §4, §12 |
| **PyInstaller** | **Installs and freezes, but the frozen product does not start:** a real freeze of this product's own dependency graph succeeds (219 MB onedir, 2 m 28 s) and the executable then dies at import inside a pydantic plugin that reads its target's source text — a plugin that is live in the product's own venv | §5, §13 |
| **No shell** | **The arrangement the project already has, measured end to end here:** a 1.05 MB wheel installs into a clean venv in 10 s and uninstalls cleanly, the service serves the workbench from its own origin, and the three guards need nothing new | §6, §11, §13 |

## 3. Electron, measured rather than assumed

- **The npm payload is a stub.** `electron@45.2.3`: `dist.unpackedSize`
  1,214,826 bytes, and the installed package holds only `index.js`,
  `install.js`, `cli.js`, `checksums.json`, `electron.d.ts` and friends.
  Crucially it declares **no lifecycle scripts at all** —
  `require('electron/package.json').scripts` is `undefined` — so a package
  manager is not "skipping" a script and no repository policy is involved
  (`web/.npmrc` carries only `save-exact` and `engine-strict`). A fresh
  `pnpm add electron@45.2.3` finished in 4 s with `dist/` empty and `path.txt`
  absent.
- **The binary arrives late, at first `require`.** `require('electron')` printed
  `Downloading Electron binary...`, took **31 s**, and afterwards `dist/` and
  `path.txt` existed. Recorded because it is a **gate-shaped** fact: an Electron
  line moves a ~100 MB-class download out of the install step and into whichever
  step first touches the package.
- **What the binary is.** Extracted: `dist/` = **365,514 KB (~357 MB)**,
  `electron.exe` = **249,831,936 bytes (~238 MB)**, alongside `ffmpeg.dll`,
  `icudtl.dat`, `snapshot_blob.bin`, `v8_context_snapshot.bin`,
  `resources.pak`, `locales/`, `vk_swiftshader.dll`, `vulkan-1.dll`,
  `d3dcompiler_47.dll`, `dxcompiler.dll`. Compare §1's 269 KB workbench and the
  existing 1.05 MB wheel: the shell is two orders of magnitude larger than the
  product it wraps. Electron's own repository says so in prose — *"Bundling …
  increases the total disk size of Electron apps (most apps are >100MB)"* — and
  that sentence is **not reachable on the published docs site**, so the number
  this record uses is the one measured here.
- **It runs.** A windowless probe reported `electron 45.2.3 / chrome
  156.0.8078.80 / node 24.22.2 / v8 15.6.75.27-electron.0`, exit 0 in 0.63 s.
  Electron 45's release notes name Chromium 156.0.8078.48 and Node v24.22.0 as
  the line's baseline; the measured values are patch bumps over it, consistent
  with the documented Node policy.
- **`engines.node >= 22.12.0` is an npm fact, not a documentation fact** — no
  Electron page states a Node engine requirement. Recorded so the record does
  not cite a document that does not say it.

## 4. Tauri, and the difference between a compiler and a toolchain

| Step | Result |
|---|---|
| `cargo add tauri` | exit 0 — **403 packages locked**; the resolved set names `tauri-runtime-wry`, `wry`, `webview2-com` (and `webkit2gtk`, `x11` for other targets) |
| `cargo fetch` | exit 0 — crate sources downloaded; `~/.cargo/registry/cache` 61.1 MB, unpacked `src` 567.9 MB |
| `cargo build` (a one-file probe crate) | **exit 101** — rustc invoked `link.exe` and got `link: extra operand '…rcgu.o'`: the `link.exe` on this PATH is **Git's Unix hard-link tool**, and rustc's own note says *"you may need to install Visual Studio build tools with the 'C++ build tools' workload"* |
| `cargo rustc -- -C linker=rust-lld` (the linker rustup ships) | **exit 101** — `rust-lld: could not open 'kernel32.lib'` (and `ntdll.lib`, `userenv.lib`, `ws2_32.lib`, `dbghelp.lib`): no Windows SDK import libraries on this machine, so **no linker in reach can produce a Windows binary** |
| `cargo check` on the Tauri graph | **exit 101 in 3.9 s** — same signature, on `serde`/`getrandom`/`erased-serde` **build scripts**. A build script is itself a host binary, so even the "check only" half of the work needs the linker |
| `pnpm exec tauri info` (the candidate's own diagnosis) | `✔ WebView2: 157.0.4341.42`, `✔ rustc/cargo/rustup`, `✘ Couldn't detect any Visual Studio or VS Build Tools instance with MSVC and SDK components` |

The last row is the measurement's independent witness: the candidate's own tool
reports what this window found by hand. What Tauri would cost is therefore not a
dependency but a **machine-wide toolchain** (VS Build Tools' C++ workload plus
the Windows SDK) and the same on every Windows CI job that would build it.
`.github/workflows/` contains **no** Rust, cargo, Tauri, Electron or PyInstaller
step today (`grep` over `.github/`), so that is an addition to the gate, not a
reuse of it.

Tauri's own documentation is consistent: *"Tauri uses the Microsoft C++ Build
Tools for development as well as Microsoft Edge WebView2. These are both required
for development on Windows."* And on the distribution side WebView2 is **not**
bundled by default — the installer *"by default download[s] the WebView2
bootstrapper and executes it if the runtime is not installed"*, with an offline
embed at ~127 MB or a fixed runtime at ~180 MB. This machine already has the
WebView2 runtime (`157.0.4341.42`), so the runtime is not the blocker; the
development toolchain is.

## 5. PyInstaller, and the freeze that does not start

- **Installable here.** PyPI is unreachable from this machine through `uv` and
  through `urllib` (both fail at the TLS handshake), and reachable through
  `curl` — recorded as a property of this machine's path to PyPI, not of PyPI.
  The wheel (`pyinstaller-6.22.3-py3-none-win_amd64.whl`, 1,454,907 bytes)
  downloaded from `files.pythonhosted.org` and installed into a scratch venv:
  `PyInstaller 6.22.3`, deps `altgraph`, `packaging`, `pefile`,
  `pyinstaller-hooks-contrib`, `pywin32-ctypes`, `setuptools`.
- **The freeze succeeds.** `frozen_probe.py` importing `labcairn.api.app.create_app`
  and `labcairn.cli.main`, frozen against **this worktree's** `src` with the
  project's real dependency set installed: exit 0 in **2 m 27.965 s**; onedir
  tree **224,176 KB (~219 MB)**, `frozen_probe.exe` **45,804,198 bytes (~43.7 MB)**.
  (A first pass against a stub venv produced 22.3 MB and failed with
  `ModuleNotFoundError: fastapi`. That failure belongs to the probe, not the
  candidate — the scratch venv held PyInstaller only — and it is kept here
  because it is the reason the honest re-run happened.)
- **The frozen executable does not start.** Running it dies at import:
  `labcairn.api.app` → `fastapi` → `fastapi.exceptions:157` →
  `pydantic.create_model` → `complete_model_class` →
  `pydantic.plugin._schema_validator` → `logfire.integrations.pydantic:354`
  (`_patch_PluggableSchemaValidator`, line 460) → `inspect.getsource` →
  **`OSError: could not get source code`**. A frozen application does not carry
  source text, and this dependency reads its target's source text at runtime.
- **This is the product's graph, not the probe's.** In the *project's* venv,
  `logfire 5.2.0` is installed and importing `fastapi` there produces
  `pydantic._internal._plugins == {'logfire.integrations.pydantic:plugin':
  LogfirePydanticPlugin()}` — the same plugin the frozen run choked on. `logfire`
  enters through the `logfire` extra of `pydantic-ai-slim` and `pydantic-evals`,
  both pulled by the declared `pydantic-ai>=1,<2`.
- **The same frozen executable starts with `PYDANTIC_DISABLE_PLUGINS=1`** set in
  the environment (prints `frozen import ok: True`, exit 0). So the failure is
  not the bootloader and not the collection step: it is one import-path plugin in
  the graph that assumes source availability. Whether the *shipped* build needs
  that flag, a build-time hook, or simply not installing the extra is
  **named-open** (O5).
- **Licence, and one absence.** PyInstaller is GPL-2.0 **with an exception**:
  *"You may use PyInstaller to bundle commercial applications out of your source
  code"*, and the bundles *"can be shipped with whatever license you want, as
  long as it complies with the licenses of your dependencies"*. What its
  documentation does **not** contain is Windows code signing: `--codesign-identity`,
  `--entitlements` and `--osx-bundle-identifier` are labelled macOS-only, and a
  full-text read found no Windows signing support. Signing is deferred behind
  `W28` for this project (`LC-P3-00` §6), so this is not disqualifying — but the
  record records that a PyInstaller route would bring no signing mechanism.
- It is also **not a cross-compiler** — *"to make a Windows app you run
  PyInstaller on Windows"* — which means a PyInstaller build product is a
  development-machine artifact, not a runner artifact.

## 6. What already exists, measured as the baseline candidate

| Artifact | Measured |
|---|---|
| `labcairn-0.1.0-py3-none-any.whl` | **1,099,635 bytes (~1.05 MB)**; sdist 6,563,310 bytes (`uv build`, hatchling) |
| installed product footprint | `site-packages` **514,074 KB** (venv 542,381 KB) |
| clean install | `uv venv --python 3.12` + `uv pip install <wheel>`: **exit 0, 10 s**, resulting venv 424,791 KB, `labcairn.exe` console script present, `import labcairn` resolving to the **installed** package rather than the source tree |
| clean uninstall | exit 0, and the import afterwards raises `ModuleNotFoundError` |
| the service serving the workbench | `labcairn serve --static-dir web/dist` exists and mounts the built bundle at the service's own origin (`app.py:448`); the rendered start-up panel prints the allow-list rather than burying it |
| the runtime requirement | `requires-python = ">=3.12,<3.13"`; the project venv is 3.12.13; the **bare** system `python` on this machine is 3.10.11 and cannot import the product at all |

That last row matters for the no-shell candidate: "just install the wheel"
presupposes a CPython 3.12 on the target machine, and this machine demonstrates
what happens when the system interpreter is not it.

## 7. The session boundary, measured against a real browser in a real shell

This is the part of the scope sentence a selection stage can actually settle, and
the part where the record differs from what it expected going in. Every request
below was read **server-side** — by an origin-echo handler for *what a request
carried*, and by the product's own service for *what its guards answered* — so a
CORS refusal in the page cannot be mistaken for a guard decision, or hide one.
The service in every row is the real `labcairn serve` started in a temporary
workspace outside the repository, on an OS-chosen port, in the shape the G1
helper starts it.

### 7.1 A page loaded from `file://` — Electron's default for a local app

| What the request carried | value |
|---|---|
| `Origin` header | **absent** — not the string `"null"` |
| `Sec-Fetch-Site` / `Sec-Fetch-Mode` | `cross-site` / `cors` |

| What the product's guards answered | result |
|---|---|
| `GET /session`, `GET /tasks`, `POST /task/select` | **403 `cross_site_refused`** on all three |

The record's first probe predicted an `Origin: null` header. **It was wrong, and
the correction matters:** Chromium sends no `Origin` at all, so the refusal comes
from the **fetch-metadata rule** (`app.py:219-229`), not from the origin
allow-list — the allow-list never saw a value to judge. Electron's own
documentation agrees in the same direction: it documents `"null"` as
`frame.origin`, not as a request header. The consequence for selection is
concrete — **naming an origin to the service would not help this arrangement**,
because there is no origin to name. Electron's documentation also discourages
`file://` outright on its own grounds (recommendation 18: such pages *"have
unilateral access to every file on your machine"*).

### 7.2 A page served from a custom standard scheme `app://labcairn`

Registered as `{ standard, secure, supportFetchAPI, stream, corsEnabled }`. A
first attempt **without** `stream` and `corsEnabled` failed to load at all
(`ERR_FAILED (-2)`); with them the page loaded and `location.origin` is
`app://labcairn`.

| | result |
|---|---|
| what the request carried | `Origin: app://labcairn`, `Sec-Fetch-Site: cross-site`, `Sec-Fetch-Mode: cors` |
| what the untold service answered | the renderer's fetches fail closed — `TypeError: Failed to fetch` — because the origin check refuses before a response is readable |
| whether the CLI can be told this origin | **no** — see §8 |

### 7.3 Electron's **main process** (`net.fetch`) — the preload-free integration path

A main-process request is not a browser-page request: it carries no `Origin` and
no fetch metadata.

| request | result | what it shows |
|---|---|---|
| `GET /session` | **200, and the body carries the token** | the service answers a client that carries no origin, and a read needs no token (`guards.py:224-228`) |
| `POST /task/select` | **401 `session_required`** | the token half of the guard holds even for the shell's own process |

**Recorded as a security-surface finding.** A shell whose main process talks to
the service can *read the session token* — that is by design, it is how the CLI
tells a person where the token is — and therefore can present it. The guard that
survives this is the token check on mutations, and it does survive. A shell
design that routes the workbench's traffic through the main process would put
the token in a Node-reachable place, which is exactly what `session.ts`'s
"module variable, never `localStorage`" reasoning avoids. **Preload/IPC tightening
is therefore not only an Electron-hygiene item; it is the item that decides
whether this finding is closed or open in the shipped product.**

### 7.4 The arrangement that needs no new origin

The shell wraps the workbench the **service itself serves**: the window loads
`http://127.0.0.1:<port>/`, the bundle comes from `--static-dir`, and the page's
origin **is** the service's own origin.

| step | result |
|---|---|
| `location.origin` in the Electron page | `http://127.0.0.1:<port>` — the service's own origin |
| `GET /health` | 200, and its `origins` field lists only the development origins plus the service's own — **no extra origin was added** |
| `GET /session` | 200, token readable to the page (the workbench's normal bootstrap) |
| `POST /task/select` without the token | **401 `session_required`** in every run |
| `POST /task/select` with `Bearer <token>` | 200 in some runs, timeouts in others — see §9 |

The renderer ran with `contextIsolation: true, nodeIntegration: false,
sandbox: true`, the token stayed in the page, and no cookie was used. Nothing in
`src/labcairn/api/` had to change for this arrangement, and nothing new was
added to the allow-list.

## 8. What the product's own CLI will be told, and what it refuses

`labcairn serve` already offers `--origin` (repeatable) and `--static-dir`.
Measured against the real command in an initialised workspace (refusal exit 3):

| `--origin` value | accepted |
|---|---|
| `app://labcairn` | **no** — *"An origin is a scheme, a host and a port — 'http://localhost:5173' — and nothing else."* |
| `file:///E:/index.html` | **no** — same refusal |
| `http://tauri.localhost` | **yes** — the printed allow-list becomes `[http://127.0.0.1:5173, http://127.0.0.1:<port>, http://localhost:5173, http://tauri.localhost]` |
| `https://tauri.localhost`, `https://app.labcairn` | **yes** |
| `http://localhost:1430`, `http://localhost:1420`, `http://localhost:5173` | **yes** |

The rule is in code, not inferred: `_check_origin` (`cli/commands.py:2373-2398`)
refuses a scheme outside `("http", "https")` and refuses anything carrying a
path, query or fragment. Consequence: **Electron's page cannot be admitted by
its natural origin spelling** (`file://`, `app://`). Electron's documentation
names the way out — register the custom scheme as `https`-privileged — and the
CLI's grammar does accept `https://app.labcairn`. A Tauri window's documented
production origin (`http://tauri.localhost`; https via
`app > windows > useHttpsScheme`) is admissible as written.

One correction to a guess recorded here: the first probe used
`http://localhost:1420` as "the Tauri dev port". **Tauri's documentation names no
such port** — its CLI's built-in dev server defaults to **1430** and its Vite
guide uses 5173. 1420 is kept in the tables only as the disproof of the guess.

## 9. The measured finding this stage did not expect: one event stream stops the whole service

Repeated against the real built workbench, the mutation that carries the token is
**not reliably answered**:

| page in the window | runs | `POST /task/select` with the token answered 200 |
|---|---|---|
| a minimal `index.html` (no application bundle) | 2 | **20 / 20**, 4–12 ms |
| the real `web/dist` | 2 | **1 / 20** — one 8 ms success, nineteen 8 s timeouts |
| the same arrangement, driven from Python instead of a page | 1 | **5 / 5**, 0.02–0.06 s |

So the endpoint is not slow: the stall appears only once the **workbench bundle
itself** is running in the page. The built bundle names `/events/stream` (a
`grep` of `web/dist/assets/*.js`), and the service documents the mechanism such
a stream produces — `routes.py:790-814`: *"The stream opens a session when it
starts and closes it when it ends… a stream that is still in a transaction holds
SQLite's **write** lock"*, with the code comment at line 814 *"let the write lock
go before the next poll"*. `LC-P3-01`'s record row 1 is the adjacent fact: on the
service the CLI starts, the event source is **`UnwiredEventSource`** — the stream
is open, and it has nothing to send.

**What is claimed and what is settled.** Measured: with a stream-less page the
write answers every time; with the real page it almost never does; from a
non-browser client it answers every time. The decisive control then landed
(operator-side record §11a): a **minimal** page with no application bundle that
opens `/events/stream` on purpose reproduces the stall — **0 / 10** mutations
answered in each of two runs, all hitting the 8 s timeout — while the same page
without the stream answers **10 / 10** in each of two runs. And a **plain-HTTP
client**, with no browser and no shell at all, reproduces it in three phases
(§11b): 6/6 before the stream, 0/6 with one long-lived stream held open, and
**0/6 even after the client closes its side of that stream**.

So the stall is **not an Electron property, not a Chromium property and not a
property of the workbench bundle**. It is a service-side failure that an event
stream triggers. `LC-P3-01`'s record row 1 and its witness
`test_the_event_stream_the_page_reads_is_unwired_in_the_service_the_cli_starts`
(`tests/test_workbench_serve_helper.py:386`) already name the adjacent defect:
the CLI starts the service with `UnwiredEventSource`, and `GET /events/stream`
raises its `not_implemented` refusal **after** the `200` and
`text/event-stream` headers have been sent, so the client sees a stream that
opens and ends empty while the service logs
`RuntimeError: Caught handled exception, but response already started.` This
window's runs reproduce that exact traceback in the service's own output.

**Two corrections the follow-up measurements forced on this record.** It first
called this a *write-path* failure caused by a *long-lived* stream. Both words
were too narrow:

1. **It is not only writes.** The 40-second control and the read/write split
   (§11c) show that after an unwired stream raises, `GET /health`, `GET /tasks`,
   `GET /session` and `GET /papers` all time out too, while the service process
   stays alive (`process alive: True`). A service that never opens a stream
   answers 6/6 writes before and 6/6 after 40 s idle, with zero tracebacks, so
   elapsed time and repeated writes are ruled out. Before any stream, 20
   concurrent `GET /health` all answer in 47 ms; after eight short streams, 20
   concurrent reads all time out (§11d).
2. **It is not only long-lived streams.** A single
   `GET /events/stream?follow=false` — the short form that returns on its first
   page and never enters the `time.sleep` poll loop — is enough to stop all
   subsequent reads and writes (§11e). So "a desktop window keeps a stream open
   continuously" is not the trigger; a stream route raising after its headers
   were sent is.

**The mechanism is still not measured, and the obvious candidates were tested and
refuted.** `routes.py:790-814` documents that a stream still in a transaction
holds SQLite's write lock, and `frames()` calls `session.rollback()` only after
`source.page()` returns — which an `UnwiredEventSource` never does — with
`finally: session.close()`. But a direct witness (§11f) asked an **independent
connection to the same database** for `BEGIN IMMEDIATE` before and after the
unwired stream raised: it succeeded in 0 ms both times, on both the control and
the experiment service. The write lock is **not** being held. Sync-worker
exhaustion is also disfavoured: a dose-response on eight independent services
(§11g) shows **one** short stream is enough to stop the service, while this
environment's AnyIO default limiter is 40 tokens (`anyio 4.15.1`, measured from
inside an event loop).

**Where the failure sits is measured.** After one short stream (§11h): a raw TCP
connection still succeeds in 16 ms and the process is alive, but `GET /health`,
`GET /docs` and `GET /openapi.json` all time out — the last two touch neither the
product's guards nor its store. So uvicorn is accepting connections and the ASGI
application has stopped serving requests. The service's second traceback passes
through `starlette/middleware/base.py:149` → `:208 raise app_exc`
(`BaseHTTPMiddleware`); the service installs one at `app.py:389`
(`@app.middleware("http")`, `_guards`, which calls `call_next`), and the first
traceback is the streaming response's collapsing task group raising
`RuntimeError: Caught handled exception, but response already started.` after
`UnwiredEventSource.page` (`events.py:87-94`) refused. Those two facts sit next
to each other in the log; **no causal claim is made here**, and no product code
was changed to test them.

**One honesty note about which tree was measured.** The console script is the
project venv's installed launcher, whose editable-install `.pth` points at the
**main checkout** (`E:\LabCairn\src` — the traceback paths say so), not at this
worktree. Checked: `git diff main..HEAD -- src/` is empty and `routes.py`,
`events.py`, `app.py` and `guards.py` have identical SHA-256 in both trees, so
the failure was measured on exactly the code this record cites (§11i).

**Bottom line for this stage:** the trigger is measured (an unwired event stream),
the scope is measured (the whole ASGI application stops answering), and the
mechanism is named-open. O6 is therefore "what the stream route leaves the ASGI
application waiting for, and what fixes it", and it belongs to whoever owns
`src/labcairn/api/` — not to the shell selection.

**Why this belongs in a *selection* record.** It is the concrete answer to "what
does a shell do to the local API session boundary": the workbench's first act in
a desktop window is to open its event stream, and on the service the CLI starts
today that one act stops the service answering anything. Whichever candidate the
owner picks, the implementation stage inherits this as a measured precondition —
and §11g/§11h show the failure is independent of the shell, so it is a
prerequisite to raise before implementation, not a cost any candidate adds. The
witness that settles it belongs with `src/labcairn/api/`, not to a probe that
happens to pass.

## 10. Named-open rows — what is not settled here, and what would settle it

Every number in this record is either measured on this machine with the command
that produced it, or one of these:

| # | Open | What would close it |
|---|---|---|
| O1 | The **clean-Windows drill** — install → launch → upgrade drill → uninstall → rollback preserving user data, on a clean environment. Measured here only in part (install and uninstall of the wheel, on a development machine that carries the project's own toolchain and pins). | The implementation stage's drill on a clean environment, per §3.6 row 3, with the evidence naming commit, package hash, OS and host versions. |
| O2 | **Binary sizes and startup cost for a Tauri build.** Its documentation states no byte figure, and nothing compiled here. | A build on a machine with the MSVC/SDK toolchain installed — which is itself an owner decision, since it changes the machine. |
| O3 | **How a Python runtime ships inside a Tauri or Electron product.** Not attempted; a shell wrapping a frozen service, a bundled interpreter, or a sidecar are three different arrangements and none was measured. | A measured trial in the implementation stage, once the shell is chosen. |
| O4 | **CI gate cost for a shell candidate.** No workflow today carries a Rust, Node-build, Electron or PyInstaller step; the shard cost table is runner-measured by rule and a local timing is not a runner cost (§3 rule 3). | The batch's runner run. A new test file would also need its three registrations, reported by this window to the commander rather than written here: none was added, because this stage adds no test file. |
| O5 | **What it takes to make a frozen build of *this* product start** — the `PYDANTIC_DISABLE_PLUGINS=1` flag, a build-time hook, or a dependency graph that does not install the `logfire` extra. | A freeze against the *installed* product's graph (not a scratch venv) plus one run with each option. |
| O6 | **What the unwired stream route leaves the ASGI application waiting for, and what fixes it.** §11a–§11h settle the trigger (one event stream, even a short `follow=false` one), the scope (all HTTP requests stop while TCP and the process stay alive, §11g one-stream dose, §11h guard-free endpoints), and rule out elapsed time (§11c) and the SQLite write lock (§11f). The mechanism is not identified; no product code was changed. | A witness that measures the service's request capacity across an unwired stream, plus a fix witnessed to restore it. **This is a service-side defect, not a shell-selection question**, and belongs with whoever owns `src/labcairn/api/` — and it should be raised before implementation, because §11h shows the failure is independent of which shell is chosen. **Cross-reference, added 2026-11-10 after this row was written:** the row was taken
up by a separate window, which identified the mechanism, fixed it and witnessed it —
`docs/acceptance/o6-event-stream-stall-2026-11-10.md`. It confirms this record's two
refutations (§11c, §11f) and its §11 readings, and it measures the pipe capacity this
record never measured. The §11 text above is left as measured. |
| O7 | **Signing.** Recorded as deferred behind `W28` (`LC-P3-00` §6); this stage records status, produces no signature. Tauri documents installer hooks, Electron documents a signing step in its distribution flow, PyInstaller documents **no** Windows signing. | The owner's decision at `W28`'s own trigger. |
| O8 | **`file://` and `app://` pages against the service in a *shipped* configuration** (the probes here were single-page scratch windows with `sandbox: true`, `contextIsolation: true`). | The implementation stage's own boundary witnesses, per §0 rule 5. |

## 11. What the record adopts

The record adopts **two things, in that order**, and the second is deliberately
narrower than a shell choice.

1. **The integration shape: the shell wraps the origin the service already
   serves.** The workbench is served by the service from `--static-dir` at the
   service's own origin, and the shell window loads that origin. Measured in
   §7.4: the three guards are unchanged, the allow-list gains nothing, the token
   stays in the page, and no `--origin` is needed. Every alternative the probes
   found costs the boundary something: a `file://` page is refused by the
   fetch-metadata rule and cannot be fixed by naming an origin; a custom-scheme
   page must be named, and Electron's natural spellings are refused by the
   product's own origin grammar; a main-process integration path can read the
   session token. "Tighten preload and IPC" (§3) is, on this evidence, *load
   the served origin and keep the workbench's own HTTP session* — and if a shell
   cannot do that, the fallback the CLI already supports is naming the shell's
   documented `http(s)` origin via `--origin`, which Tauri's spelling satisfies
   and Electron's does not.

2. **The candidate ranking, as a ranking rather than a choice:** **Electron is
   the only shell candidate buildable on this machine as it stands** (§3, §4,
   §5), so it is the candidate a selection stage can prototype against without
   changing the machine. That is a statement about this machine's toolchain, not
   an endorsement: its cost is a 357 MB per-app Chromium and Node, a ~100 MB
   binary that arrives at first `require` rather than at install, and the §7.3
   token-reachability finding. **Tauri is not buildable here at all** and would
   cost a machine-wide MSVC/SDK toolchain plus the same on every Windows CI job
   that builds it. **PyInstaller's app-freeze path does not currently produce a
   product that starts.** **No shell** costs nothing new and is the arrangement
   the browser baseline already measured.

The record does **not** adopt a dependency, and it adds none: a new desktop
dependency is an owner decision under §3 rule 4, and this window edited no
manifest. If the owner's answer is "no shell for now", §3.2 already says the
selection stage is still a complete result.

## 12. What a candidate's refusal means

§10 asks the record to say what refusing a candidate costs, rather than leaving
it as a gap.

- **Refusing Electron.** The workbench stays served by the service; the desktop
  convenience items (a single application icon, file opening from a shell menu,
  an application menu, single-instance lifecycle) go unimplemented in Phase 3,
  and the "Distribution and review" row of execution plan §4 is carried by an
  install-and-launch arrangement rather than by a packaged app. Nothing else in
  Phase 3 changes: §3.5 records that `LC-P3-06` neither waits on `LC-P3-05` nor
  unblocks it, and `LC-P3-08`'s trial runs against whatever build exists — so a
  refused shell must still leave an *installed, launchable, drillable* build,
  which is the no-shell row of §6 plus the §10 O1 drill.
- **Refusing Tauri now but not forever.** The measured blocker is a missing
  toolchain, not a property of the candidate. What refusing it now means is that
  the MSVC/SDK decision — a machine-wide install and a new CI step — stays with
  the owner at the trigger where a runner would have to carry it, and the
  capability-system advantage Tauri documents (per-window command allow-lists
  with scopes such as `$HOME/*`) is not exercised in Phase 3.
- **Refusing PyInstaller.** The cheapest and least consequential refusal: its
  install footprint advantage was never the reason to consider it, its Windows
  signing support does not exist in its own documentation, and it is not a
  cross-compiler. What is lost is the "one executable" distribution shape, and
  what is kept is the wheel-plus-venv arrangement the project already has and
  already gates.
- **Refusing "no shell".** Then a shell is built **and** §10's O1..O3, O5 and O6
  stop being named-open and become implementation work with witnesses. That is
  the honest shape of the choice: the no-shell row is not a free option either,
  it is the option whose costs the other three are measured against.

## 13. Boundaries this stage kept

No product code was written; no `pyproject.toml`, `uv.lock`,
`web/package.json`, `web/pnpm-lock.yaml`, CI workflow or registration file was
touched. No dependency was added to the product. No material text of the pilot
corpus is in this record — the probes carried synthetic task titles only. Every
temporary artifact, probe and run log lives outside the repository. No test file
was added, so §3 rule 3's three registrations are not owed by this record; the
implementation stage will owe them for whatever it adds.

**Disclosure, as §10 requires.** The vendor-documentation reading behind §4, §5,
§8 and §12 was performed by an **agent session** (a `general-purpose` Claude Code
subagent with web fetch and search) on 2026-11-10 at this window's instruction;
this window did not read those pages itself. Where a documentation row could be
checked against a measurement taken here, it is marked as matching (the
`app://labcairn` origin and the `stream`/`corsEnabled` failure; the `"null"`-is-
`frame.origin` correction against the measured absent header; Chromium 156 /
Node 24.22 against the probe's version report). The raw fetched pages and the
sparse clones of the three documentation repositories are kept outside the tree
at `E:\labcairn-local\docfetch-20261110\`. Documentation rows the agent searched
for and did **not** find are recorded as absent rather than omitted: no byte
figure for a Tauri binary anywhere in its docs; no cross-candidate size, memory
or startup comparison in any of the three; no Electron guidance for a page
fetching a `127.0.0.1` API; no PyInstaller one-dir/one-file trade-off table
beyond the two-process mechanics; no PyInstaller Windows signing.

## 14. What the next window inherits

1. §11's integration shape, as a constraint to witness rather than a suggestion.
2. §7.3's token-reachability finding: preload/IPC tightening has a specific
   subject — keep the token out of the main process.
3. §9's failure and O6: one unwired event stream stops the whole ASGI
   application answering (§11g one-stream dose, §11h guard-free endpoints).
   This is the first thing to raise with `src/labcairn/api/`, independently of
   whichever shell is chosen; the mechanism and fix are named-open.
4. §10's named-open list, unchanged, as the implementation stage's opening
   inventory.
5. The board row stays where it is. It moves with the owner's dispatch.
