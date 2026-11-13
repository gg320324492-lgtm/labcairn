# ADR-0023 — A desktop shell wraps the origin the service already serves
**Line numbers.** The `file:line` pointers in this record name the lines as they stood on 2026-11-10; the tree has moved since. Follow the sentence, not the number.  
**Status:** Accepted (2026-11-10, owner's Electron selection) — the integration
shape, the candidate ranking and the contracts below are the decision;
implementation is a separate window and is not claimed here
**Work order:** `LC-P3-05` §10 (`docs/plans/PHASE_3-work-orders.md`), Phase 3 G3
— the selection and measurement stage, and the plan for the implementation stage
**Date:** 2026-11-10 · accepted 2026-11-10
**Drafted against:** local `main` at
`26f816b2ecaf03a3d62b914d685edd4f54e0356b` ("the real sample is picked from the
corpus registry"); local `main` is ahead of `origin/main`
`571e4346a03374e166f3ab67d0067eb0e632dd52` (merge of PR #153) at draft time, and
`git status --porcelain` was 0 lines.

**Number, re-checked rather than carried.** The newest ADR in the tree at draft
time is `ADR-0022-platform-conditional-code-keeps-one-reachable-body.md`;
`ls docs/adr/ADR-0023*` returned nothing. §3.4 of the work orders required the
re-check and this ADR performed it.

**Acceptance note (2026-11-10).** The owner has chosen **Electron** as the shell
to build. This ADR's measurements are what the choice was made against, not the
choice itself: the selection record deliberately stopped at a ranking (§11:
"the record adopts none of them as a dependency", and the shell choice belongs
to the owner), and its §3/§11 name Electron as the only candidate buildable on
this machine as it stands. The choice changes this ADR's status, not its
measurements: the integration shape the ADR decided is the shape Electron is to
be built in — the window loads the served origin, with no `file://` page, no
custom scheme and no `--origin` widening. **O6 is closed.** The selection record's "raise this before
implementation" precondition is discharged by the separate O6 window, which
identified the mechanism (the service wrote 6,205 bytes of traceback per
unwired stream into an unread 4,096-byte pipe), fixed it and witnessed it —
`docs/acceptance/o6-event-stream-stall-2026-11-10.md`; the cross-reference in
the selection record's §10 O6 row is the live pointer. The service-side risk
section below is kept as the measurement it was, with a note at each point the
precondition is now discharged. Implementation is planned, not performed, in
`docs/plans/LC-P3-05-shell-implementation-plan.md`.

**What this ADR decides, and what it does not.** It decides the **integration
shape** — how a desktop shell relates to the local API session boundary — and
records what each candidate costs. At drafting time it did **not** decide which
shell to build; the owner's Electron selection recorded above settled that. It
does not adopt a dependency (a new desktop dependency remains an owner
decision under §0 rule 4 / §3 rule 4), does not write product code, and does not
move the board's `LC-P3-05` row. Every measurement cited here is documented in
`docs/acceptance/LC-P3-05-selection-measurement-2026-11-10.md`, which cites its
raw commands to a record kept outside the repository; a reader who wants to know
whether a claim still holds should read that file rather than believe this one.

## Context and concrete problem

`LC-P3-05`'s scope sentence (execution plan §3) names the surface: *"Reuses the
workbench, tightens preload and IPC, navigation, file opening, runtime lifecycle
and local API session boundaries."* The last clause is not a feature of the
shell — it is the boundary `docs/THREAT-MODEL.md` §3 draws, carried by three
guards: the bind address, the origin check, and the session token
(`src/labcairn/api/guards.py`, `src/labcairn/api/app.py:196-238`).

The workbench already runs against those guards in the shape that makes the
origin check mean something: in production the service serves the built bundle
from its own origin, so page and API share one origin (`app.py:448`,
`web/src/api/base.ts`), and the only arrangement the service is *told* about is
the development server's (`extra_origins`, `cli/commands.py:2358-2398`). A
desktop shell is the first client that would keep the workbench open
continuously from outside that arrangement.

The concrete problem the selection stage had to settle is therefore not "which
framework" but: **what does each candidate do to the three guards, and what does
the product have to change to admit it?** The measurements answered it
differently for each candidate, and differently from what the window expected.

## Alternatives, including simpler/no-dependency option

### A. No shell (the option with no new dependency)

Measured, not assumed: the wheel is 1,099,635 bytes; it installs into a clean
Python 3.12 venv in 10 s and uninstalls cleanly; the service serves the 269 KB
built workbench at its own origin; the guards need nothing new. Its cost is also
measured and it is not zero: `requires-python = ">=3.12,<3.13"`, while this
machine's bare system `python` is 3.10.11 and cannot import the product — so the
arrangement presupposes a runtime the target machine must already have. There is
no application icon, no shell file-open entry, no application menu, no
single-instance lifecycle.

### B. Electron

Measured here: it builds and runs today. `electron@45.2.3`'s npm payload is a
1.2 MB stub that declares **no lifecycle scripts**, and the binary arrives at
first `require` (31 s) rather than at install. The extracted binary directory is
**357 MB**, of which `electron.exe` is **249,831,936 bytes** — Chromium and Node
shipped per app, on top of a product whose own installed `site-packages` is
already 514 MB. A windowless run reported Electron 45.2.3 / Chromium
156.0.8078.80 / Node 24.22.2 in 0.63 s.

Its session-boundary cost is the interesting part, and it is asymmetric:

- A page loaded from `file://` sends **no `Origin` header** and carries
  `Sec-Fetch-Site: cross-site`, `Sec-Fetch-Mode: cors`. The service answers
  **403 `cross_site_refused`** to `/session`, `/tasks` and `/task/select`. The
  refusal comes from the fetch-metadata rule, so **naming an origin would not
  help** — there is no origin to name. Electron's own documentation discourages
  `file://` for exactly this class of reason (its pages *"have unilateral access
  to every file on your machine"*).
- A page on a custom standard scheme has `location.origin == app://labcairn` and
  sends `Origin: app://labcairn`; the untold service refuses it. The product's
  own CLI **refuses that spelling**: `_check_origin` admits only `http`/`https`
  with no path. Electron's documented way out is registering the scheme
  `https`-privileged, which the CLI's grammar does accept (`https://app.labcairn`).
- The **main process** (`net.fetch`), i.e. a preload-free integration, carries no
  origin and no fetch metadata: `GET /session` returns **200 with the token**,
  `POST /task/select` returns **401 `session_required`**. So the shell's own
  process can read the session token and cannot bypass the mutation guard.

### C. Tauri

Measured here: **it cannot be built on this machine at all.** `cargo add tauri`
resolves (403 crates locked, 567.9 MB of crate sources fetched) and `cargo fetch`
succeeds, but `cargo build` exits 101 because the `link.exe` on this PATH is
**Git's Unix hard-link tool**, `-C linker=rust-lld` exits 101 because the Windows
SDK import libraries (`kernel32.lib` and friends) are absent, and `cargo check`
exits 101 in 3.9 seconds on *build scripts* — which are themselves host
binaries. Tauri's own CLI reports the same diagnosis independently:
`✔ WebView2: 157.0.4341.42`, `✔ rustc/cargo/rustup`, `✘ Couldn't detect any
Visual Studio or VS Build Tools instance with MSVC and SDK components`.

The blocker is a **machine-wide toolchain** (VS Build Tools' C++ workload plus
the Windows SDK), not a package. Its documentation says so: *"Tauri uses the
Microsoft C++ Build Tools for development as well as Microsoft Edge WebView2.
These are both required for development on Windows."* On the distribution side
WebView2 is not bundled by default (the installer downloads the bootstrapper
unless it is told otherwise; the offline embed is ~127 MB, a fixed runtime
~180 MB). No byte figure for a Tauri binary exists in its documentation, and
none was measured, because nothing compiled.

What Tauri would bring is documented and relevant to this ticket's "tightens
preload and IPC" clause: a capability/permission system where *"Capabilities
define which permissions are granted or denied for which windows or webviews"*,
with command allow-lists and scopes (`$HOME/*`), and *"By default the API is only
accessible to bundled code shipped with the Tauri App"*. That is a stronger
native-API boundary than Electron's `contextBridge` arrangement requires a project
to build for itself. It is recorded here and not claimed as an advantage realised
in Phase 3.

### D. PyInstaller (freeze the product into an executable)

Measured: it installs from a downloaded wheel (6.22.3), and a real freeze of
**this product's own dependency graph** succeeds — 219 MB onedir, 45,804,198-byte
executable, 2 m 27.965 s. The frozen executable then **dies at import**:
`fastapi` → `pydantic.create_model` → `pydantic.plugin._schema_validator` →
`logfire.integrations.pydantic` → `inspect.getsource` → `OSError: could not get
source code`. A frozen application does not carry source text and this plugin
reads its target's source text at runtime. The plugin is in the **product's**
graph, not an artifact of the probe: in the project venv, `logfire 5.2.0` is
installed and `import fastapi` there yields
`{'logfire.integrations.pydantic:plugin': LogfirePydanticPlugin()}`. The same
frozen executable runs cleanly with `PYDANTIC_DISABLE_PLUGINS=1`.

Its licence is workable (GPL-2.0 with the exception that *"You may use PyInstaller
to bundle commercial applications out of your source code"*), it is not a
cross-compiler, and its documentation contains **no Windows code signing** —
`--codesign-identity` and `--entitlements` are macOS-only.

## Upstream evidence (reference only)

Nothing was copied or adapted from any of these; the entries record where the
documentation-side claims come from, as §3's rules require. Documentation reading
in this stage was performed by an **agent session** on 2026-11-10 (see the
selection record's §13 disclosure); rows this window could check against its own
measurements are marked *confirmed by measurement*.

- Tauri — `https://v2.tauri.app/start/prerequisites/`,
  `https://v2.tauri.app/distribute/windows-installer/`,
  `https://v2.tauri.app/security/capabilities/`,
  `https://v2.tauri.app/security/permissions/`,
  `https://v2.tauri.app/reference/cli/`,
  `https://v2.tauri.app/start/migrate/from-tauri-1/`,
  `https://v2.tauri.app/concept/inter-process-communication/`,
  `https://v2.tauri.app/blog/tauri-2.12/`. Observed: MSVC Build Tools and
  WebView2 required for Windows development; production origin
  `http://tauri.localhost` (https via `app > windows > useHttpsScheme`); the CLI's
  built-in dev server defaults to **1430** (no documented 1420 — *confirmed by
  measurement as the disproof of this window's first guess*); MSRV 1.90 with a
  `(stable − 3)` policy, and the crates.io sparse index naming `rust_version 1.95`
  for the newest published entry. No byte figure for a binary. No commit SHA was
  inspected for these pages.
- Electron — `https://electronjs.org/docs/latest/tutorial/security`,
  `.../tutorial/fuses`, `.../api/protocol`,
  `.../api/structures/custom-scheme`, `.../api/web-frame-main`,
  `https://www.electronjs.org/blog/electron-45-0`, and
  `https://raw.githubusercontent.com/electron/electron/main/docs/why-electron.md`
  (the `>100MB` sentence, which is **not reachable on the published docs site**).
  Observed: `contextIsolation` default since 12.0.0 and mandatory alongside
  `nodeIntegration: false`; do not expose raw `ipcRenderer`; validate the IPC
  sender's **origin**, not its URL; `file://` discouraged; `"null"` is documented
  as `frame.origin`, **not** as a request header — *confirmed by measurement*
  (the measured requests carried no `Origin` at all); a standard-scheme page gets
  a real origin and `corsEnabled` defaults false — *confirmed by measurement*
  (without `stream`/`corsEnabled` the page failed to load; with them
  `location.origin` was `app://labcairn` and requests carried that origin);
  Electron 45 names Chromium 156.0.8078.48 and Node v24.22.0 — *confirmed at patch
  level by measurement* (156.0.8078.80 / 24.22.2). `engines.node >= 22.12.0` is an
  npm publication fact; no documentation states it.
- PyInstaller — `https://pyinstaller.org/en/stable/license.html`,
  `.../usage.html`, `.../feature-notes.html`, `.../advanced-topics.html`,
  `.../hooks.html`. Observed: the GPL exception quoted above; `--onedir` default
  and `--onefile`'s two-process temporary extraction; `--add-data`,
  `--hidden-import`, `--collect-*`; hooks exist because *"PyInstaller cannot
  reliably find all the needed files"*; signing documented for macOS only; not a
  cross-compiler.
- Licences, as recorded rather than asserted: Electron MIT; Tauri's crate line
  (MIT/Apache-2.0 dual) and `@tauri-apps/cli` 2.12.4 / `@tauri-apps/api` 2.12.4;
  PyInstaller GPL-2.0-with-exception plus Apache-2.0 for a few files. No licence
  text was copied into this repository. **No dependency was added to the product
  by this stage and none is proposed for a manifest here.**

## Decision and why this fits LabCairn

**Decision (the shape, not the framework).** A desktop shell for LabCairn wraps
**the origin the service already serves**: the built workbench is mounted by the
service at its own origin (`--static-dir`), the shell window loads that origin,
and the shell's native surface is reached through a preload/IPC layer that never
carries the session token. The service's allow-list stays as it is.

Why this fits, measured rather than argued:

1. **It is the only arrangement measured to leave all three guards untouched.**
   The page's origin was the service's own (`http://127.0.0.1:<port>`), the
   `/health` allow-list gained nothing beyond the development origins, the token
   was readable to the page exactly as the workbench's own bootstrap expects, a
   mutation without the token was refused **401 `session_required` in every run**,
   and nothing in `src/labcairn/api/` had to change.
2. **The alternatives each cost the boundary something measurable.** `file://` is
   refused by the fetch-metadata rule and is not fixable by naming an origin. A
   custom-scheme page must be admitted, and Electron's natural spellings
   (`file://`, `app://`) are refused by the product's **own** origin grammar —
   `_check_origin` admits only `http`/`https` with no path. A main-process
   integration path can *read* the session token, which is the property
   `web/src/api/session.ts` is written to deny ("module variable, never
   `localStorage`").
3. **It matches the project's existing security stance instead of adding a new
   one.** The origin check is load-bearing in `docs/THREAT-MODEL.md` §3.2, and an
   arrangement that keeps page and API same-origin keeps that claim exactly as
   `LC-P3-01` baselined it. `--origin` remains the documented escape hatch — and
   the measurement says which candidate's spelling it admits (Tauri's yes,
   Electron's natural ones no).
4. **It kept "no shell" live at selection time.** The shape is a constraint on a
   shell, not a commitment to one, and §3.2 states that the selection stage is a
   complete result even if the owner defers the shell. The owner's Electron
   selection (acceptance note above) exercises the shape rather than retiring
   this property: a later decision not to build a shell would still leave the
   product exactly as the browser baseline measured it.

**What the selection stage's evidence says about the candidates, ranked on this
machine's evidence and nothing else:** Electron is the only candidate buildable
here today (and therefore the only one a selection window could prototype
against); Tauri requires a machine-wide toolchain decision; PyInstaller's
app-freeze path currently produces an executable that does not start. The record
adopts none of them as a dependency — a new desktop dependency is an owner
decision under §0 rule 4, and this ADR's acceptance is not that approval. The
implementation plan records the package, version, licence and lockfile change
for the owner's approval before any manifest is edited.

## Risks, tradeoffs and reversibility

- **The measured stall is the largest risk, and it is not the shell's.** Against
  the real built workbench, the token-bearing `POST /task/select` answered 200 in
  **1 of 20** attempts (nineteen 8 s timeouts); against a minimal page **20 of
  20** (4–12 ms); from a non-browser client **5 of 5** (0.02–0.06 s). A decisive
  control settled the correlation: a minimal page that opens `/events/stream` on
  purpose answers **0 of 10** mutations in each of two runs, while the same page
  without the stream answers **10 of 10** in each of two; and a plain HTTP client
  with no browser and no shell answers 6/6 before a stream, 0/6 during it, and
  **0/6 even after its side of the stream is closed**. So the failure is
  **service-side**, not a property of Electron, Chromium or the workbench bundle.
  `LC-P3-01`'s row 1 and `test_workbench_serve_helper.py:386` already record the
  adjacent defect (`UnwiredEventSource` refusing after the stream's headers are
  sent); this window's runs reproduce its `RuntimeError: Caught handled
  exception, but response already started.` in the service's own output.

  Two follow-up measurements corrected the narrow description "write path" and
  "long-lived": after an unwired stream raises, `GET /health`, `/tasks`,
  `/session` and `/papers` all time out too while the process stays alive; and a
  single short `GET /events/stream?follow=false` is enough — a dose-response on
  eight independent services shows **one** short stream stops the service. A
  no-stream control answers 6/6 before and 6/6 after 40 s idle with zero
  tracebacks, and 20 concurrent reads answer in 47 ms before any stream but all
  time out after eight short ones. `routes.py:790-814` documents that a stream
  still in a transaction holds SQLite's **write** lock, but a direct witness
  asked an independent connection to the same database for `BEGIN IMMEDIATE`
  before and after the stream raised: it succeeded in 0 ms both times. **The
  write lock is not the cause**, and sync-worker exhaustion is disfavoured (one
  stream versus a measured 40-token AnyIO limiter). After one short stream, a
  raw TCP connection still succeeds in 16 ms while `/health`, `/docs` and
  `/openapi.json` all time out — the last two touch neither the guards nor the
  store — so the failure sits in the ASGI application. Its second traceback
  passes through `starlette/middleware/base.py:149→:208`
  (`BaseHTTPMiddleware`, installed at `app.py:389`); the first is the streaming
  response's collapsing task group raising `RuntimeError: Caught handled
  exception, but response already started.` **No causal claim is made, the
  mechanism is not identified, and no product code was changed.**

  **At drafting time, a desktop shell that opens the workbench's event stream
  stopped the service answering anything.** A shell built on top of this
  without closing that gap would look like the shell's defect and be the
  service's. The trigger and scope were measured; the mechanism and fix were
  named-open and belonged to `src/labcairn/api/`, not to this ADR — and were to
  be raised before implementation, since the failure was independent of the
  shell.

  **Discharged (2026-11-10).** O6 is closed. The mechanism is measured: the
  refusal was raised after the response headers had gone out, so the service
  wrote 6,205 bytes of traceback per short unwired stream into a captured pipe
  of measured 4,096-byte capacity that nobody read; the writer parked in the
  full pipe, and the event loop served nothing. The fix refuses the stream
  before its headers (403 `not_implemented` on both `GET /events` and
  `GET /events/stream`) and is held by
  `tests/test_api_concurrency.py::test_one_unwired_event_stream_leaves_the_service_able_to_answer`,
  which drains one arm and leaves the other's pipe unread on purpose. See
  `docs/acceptance/o6-event-stream-stall-2026-11-10.md`. This ADR's
  service-side paragraphs above are the selection stage's snapshot and are
  left as measured. **The shell-side obligation survives the fix**: a client
  that captures a child's stdout/stderr in a pipe must drain both, because a
  service can write output for reasons other than one fixed defect — this is
  the hard rule of `docs/plans/LC-P3-05-shell-implementation-plan.md` §3.
- **Token reachability in a Node-reachable process.** Measured on Electron's main
  process: `GET /session` returns the token to a client carrying no origin. That
  is the service behaving as designed (the CLI needs to point a person at the
  token), and the mutation guard held. The risk is a shell design that routes the
  workbench's traffic through the main process and thereby places the token
  somewhere Node-reachable. The decision above closes this by construction;
  it needs a witness to hold, not just a sentence.
- **Footprint, honestly counted.** Electron's per-app Chromium and Node (357 MB
  measured, 238 MB of it one executable) against a 1.05 MB wheel and a 269 KB
  bundle. Tauri's promise is the opposite by design — *"rel[y] on the operating
  system WebView and not bundling the WebView into the application binary"* —
  and its docs state no byte figure, so this record states none.
- **Binary distribution outside the registry.** Electron's binary is a
  second-channel ~100 MB-class download that lands at first `require`, not at
  install; Tauri's installer fetches a WebView2 bootstrapper by default. Both
  change what a build and a CI job have to reach for. Today `.github/workflows/`
  contains no Rust, Node-build, Electron or PyInstaller step at all.
- **A toolchain is not a dependency.** Choosing Tauri means installing MSVC Build
  Tools and the Windows SDK on this machine and on every Windows job that builds
  it. That is a machine decision with consequences beyond this ticket, which is
  why it is stated as the owner's rather than absorbed here.
- **Reversibility is high and the record says why.** No manifest, lockfile, CI
  file or registration file was touched; no test file was added; the shell layer
  would sit outside `src/labcairn/`'s existing packages and above the HTTP
  boundary the product already enforces, so removing it returns the product to
  exactly what it is today. The shape decision also does not close the other
  routes: if the owner picks a custom-scheme Electron build, the cost is one
  documented `--origin` value in an `https` spelling, which the CLI already
  admits.
- **Signing is untouched.** Deferred behind `W28` per `LC-P3-00` §6. Recorded for
  the record's completeness: Tauri documents installer hooks, Electron documents
  a signing step in its distribution flow, PyInstaller documents no Windows
  signing.

## Contracts and acceptance tests

No witness is added by this ADR or by the selection stage — this stage writes
records, not product code, and it adds no test file (so §3 rule 3's three
registrations are not owed here). What the decision commits the implementation
stage to, in the project's own terms, is this list; each entry is a claim that
needs a witness that fails when the property is broken:

1. **The shell's page is same-origin with the service.** A witness asserts the
   loaded page's origin equals the service's own origin, and that the allow-list
   carries no extra entry the service was not asked for. It fails if the shell
   starts loading a `file://` or custom-scheme page.
2. **A mutation without the token is refused from inside the shell.** Measured
   today as 401 `session_required` in every run; the witness keeps it true when
   preload and IPC are written.
3. **The session token is not reachable from the shell's native layer.** A
   witness for the preload/IPC contract: the token travels page → HTTP header and
   never through the main process, and a native API surface cannot read it.
   Electron's own guidance names the failure mode (exposing raw `ipcRenderer`,
   and validating the sender's **origin** rather than its URL).
4. **The service keeps answering requests after the workbench opens its event
   stream.** The §"Risks" failure, turned into a witness owned by
   `src/labcairn/api/`: one short stream, then a token-bearing mutation **and** a
   read (including a guard-free endpoint), all answered. **Satisfied
   2026-11-10**, by the separate O6 window rather than by the shell stage:
   `docs/acceptance/o6-event-stream-stall-2026-11-10.md` §4 names the witness,
   its drained/undrained arms and its two counter-mutations. This was a
   prerequisite to shell implementation, not a shell witness — §11g/§11h had
   shown the failure without any shell at all. The shell stage still owes its
   own witness for the pipe-draining rule (plan §3, AC-3), because a fixed
   service does not make an unread pipe safe.
5. **Install, launch, upgrade drill, uninstall and rollback preserving user
   data** on a clean Windows environment, with the evidence naming commit,
   package hash, OS and host versions (§3.6 row 3, execution plan §4's
   "Distribution and review" row). Today only install and uninstall of the wheel
   are measured, on a development machine.
6. **The shell is not a route into a DOCX host.** §3.3 of the work orders applies
   with special force: no COM, ProgID or UI automation of WPS or Word becomes
   available through the shell. A candidate whose only DOCX integration is
   automation is a recorded finding against that candidate, not an exception.
7. **The bundle still names no remote host.** `web/src/api/bundle.test.ts`
   already watches the built bytes against two allowed hosts; a shell that adds a
   dependency carrying a remote host reddens it, and the shell's own dependencies
   are subject to the same reading.

## Re-evaluation trigger

- **A runner, not this machine.** The shard-cost rule says a local timing is not
  a runner cost. If a shell candidate is implemented, its CI cost is measured on
  a runner, and this ADR's footprint claims are re-measured at that commit —
  a claim about one commit does not carry to another.
- **A Tauri-capable machine.** If MSVC Build Tools and the Windows SDK are
  installed by the owner's decision, §"Alternatives" option C's blocking claim
  ("not buildable here") stops being true and the ranking in §"Decision" has to
  be re-derived from measurements rather than inherited from this record.
- **An Electron major bump.** Electron's Node and Chromium lines move under a
  documented policy, and the measured pairing (45.2.3 → Chromium 156.0.8078.80,
  Node 24.22.2) is a snapshot at one version; §7's origin behaviour should be
  re-measured at a bump, not assumed to survive it.
- **`W28`'s signing trigger.** Signing and public distribution are owner
  decisions at their own trigger (`LC-P3-00` §6). When that trigger opens, the
  per-candidate signing facts recorded here are re-read, and PyInstaller's
  documented absence of Windows signing becomes a live constraint rather than a
  note.
- **The stall's cause was settled on 2026-11-10.** O6 came back with a cause
  that is the event stream, in the specific form of traceback bytes written
  after headers into an unread pipe (`docs/acceptance/o6-event-stream-stall-2026-11-10.md`
  §2). The risk section's first bullet describes the pre-fix service and is
  annotated, not rewritten. If a later measurement overturns that mechanism,
  this ADR is amended rather than left holding an attributed cause.
- **A new candidate arrives, or the owner names one.** This ADR ranks four
  arrangements measured on one machine on 2026-11-10. A fifth is a reason to
  re-measure, not a reason to extend this ranking by inference.
